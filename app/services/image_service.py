from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from app.core.database import Database
from app.core.meal_rules import infer_is_meal
from app.models.image import Image
from app.repositories.images import ImageRepository
from app.services.llm_service import LLMService
from app.services.media_storage import MediaStorageService
from app.services.streak_service import sync_user_streak
import logging

logger = logging.getLogger(__name__)


def _meal_name_from_analysis(analysis: Dict) -> Optional[str]:
    raw = analysis.get("meal_name")
    if raw is None:
        return None
    s = str(raw).strip()[:255]
    return s or None


class ImageService:
    def __init__(self, db: Database):
        self.db = db
        self.llm_service = LLMService()
        self.media_storage = MediaStorageService()

    def _sync_streak_safe(self, user_id: str) -> None:
        try:
            sync_user_streak(self.db, user_id)
        except Exception:
            logger.exception("sync_user_streak failed for user_id=%s", user_id)

    async def upload_and_analyze_image(
        self,
        file_obj,
        user_id: str,
        original_filename: str,
        file_size: int,
        content_type: str,
        user_description: str = None,
    ) -> Dict:
        try:
            file_obj.seek(0)
            image_content = file_obj.read()
            file_obj.seek(0)

            upload_result = self.media_storage.upload_file(file_obj, user_id, original_filename)

            if not upload_result["success"]:
                return {"error": upload_result["error"]}

            image = Image.new(
                filename=upload_result["filename"],
                original_filename=upload_result["original_filename"],
                file_url=upload_result["file_url"],
                s3_key=upload_result["s3_key"],
                s3_bucket=upload_result["bucket"],
                file_size=file_size,
                content_type=content_type,
                owner_id=user_id,
            )
            self.db.images.create(image)

            analysis = await self.llm_service.analyze_image_content(
                image_content, content_type, description=user_description
            )
            logger.debug("Analysis result keys: %s", list(analysis.keys()))

            calories = analysis.get("calories", 0)
            exercise_recommendations = analysis.get(
                "exercise_recommendations",
                {"steps": int(calories * 20), "walking_km": round(calories / 50, 2)},
            )

            image.is_food = analysis.get("is_food", False)
            image.is_meal = infer_is_meal(
                image.is_food,
                analysis.get("confidence", 0.0),
                analysis.get("food_items", []),
            )
            image.analysis_description = analysis.get("description")
            image.food_items = analysis.get("food_items", [])
            image.estimated_calories = calories
            image.nutrients = analysis.get("nutrients", {})
            image.analysis_confidence = analysis.get("confidence", 0.0)
            image.analysis_completed = datetime.now(timezone.utc)
            image.meal_name = _meal_name_from_analysis(analysis)
            image.description = analysis.get("description")

            self.db.images.save(image)
            self._sync_streak_safe(user_id)

            image_dict = image.to_dict()
            if "analysis" in image_dict:
                image_dict["analysis"]["exercise_recommendations"] = exercise_recommendations

            return {"success": True, "image": image_dict}

        except Exception as e:
            logger.exception("upload_and_analyze_image failed")
            return {"error": f"Upload and analysis failed: {str(e)}"}

    async def upload_image_only(
        self, file_obj, original_filename: str, file_size: int, content_type: str, user_id: str
    ) -> Dict:
        try:
            file_obj.seek(0)
            upload_result = self.media_storage.upload_file(file_obj, user_id, original_filename)

            if not upload_result["success"]:
                return {"error": upload_result["error"]}

            image = Image.new(
                filename=upload_result["filename"],
                original_filename=upload_result["original_filename"],
                file_url=upload_result["file_url"],
                s3_key=upload_result["s3_key"],
                s3_bucket=upload_result["bucket"],
                file_size=file_size,
                content_type=content_type,
                owner_id=user_id,
            )
            self.db.images.create(image)

            return {"success": True, "image": image.to_dict()}

        except Exception as e:
            logger.exception("upload_image_only failed")
            return {"error": f"Upload failed: {str(e)}"}

    async def upload_image_with_analysis(
        self,
        file_obj,
        original_filename: str,
        file_size: int,
        content_type: str,
        user_id: str,
        analysis: Dict,
    ) -> Dict:
        try:
            file_obj.seek(0)
            upload_result = self.media_storage.upload_file(file_obj, user_id, original_filename)

            if not upload_result["success"]:
                return {"error": upload_result["error"]}

            fi = analysis.get("food_items", [])
            is_food = analysis.get("is_food", False)
            conf = analysis.get("confidence", 0.0)
            image = Image.new(
                filename=upload_result["filename"],
                original_filename=upload_result["original_filename"],
                file_url=upload_result["file_url"],
                s3_key=upload_result["s3_key"],
                s3_bucket=upload_result["bucket"],
                file_size=file_size,
                content_type=content_type,
                owner_id=user_id,
                is_food=is_food,
                is_meal=infer_is_meal(is_food, conf, fi),
                analysis_description=analysis.get("description"),
                food_items=fi,
                estimated_calories=analysis.get("calories", 0),
                nutrients=analysis.get("nutrients", {}),
                analysis_confidence=conf,
                analysis_completed=datetime.now(timezone.utc),
                meal_name=_meal_name_from_analysis(analysis),
            )
            self.db.images.create(image)
            self._sync_streak_safe(user_id)

            return {"success": True, "image": image.to_dict()}

        except Exception as e:
            logger.exception("upload_image_with_analysis failed")
            return {"error": f"Upload failed: {str(e)}"}

    async def update_image_analysis(self, image_id: str, analysis: Dict) -> Dict:
        try:
            image = self.db.images.get_by_id(image_id)
            if not image:
                return {"error": "Image not found"}

            fi = analysis.get("food_items", [])
            is_food = analysis.get("is_food", False)
            conf = analysis.get("confidence", 0.0)
            image.is_food = is_food
            image.is_meal = infer_is_meal(is_food, conf, fi)
            image.analysis_description = analysis.get("description")
            image.food_items = fi
            image.estimated_calories = analysis.get("calories", 0)
            image.nutrients = analysis.get("nutrients", {})
            image.analysis_confidence = conf
            image.analysis_completed = datetime.now(timezone.utc)
            if "meal_name" in analysis:
                image.meal_name = _meal_name_from_analysis(analysis)

            self.db.images.save(image)
            self._sync_streak_safe(image.owner_id)

            return {"success": True, "image": image.to_dict()}

        except Exception as e:
            logger.exception("update_image_analysis failed")
            return {"error": f"Update failed: {str(e)}"}

    async def analyze_existing_image(self, image_id: str, user_id: str) -> Dict:
        try:
            image = self.db.images.get_by_id_and_owner(image_id, user_id)
            if not image:
                return {"error": "Image not found or access denied"}

            image_content = self.media_storage.get_file_content(image.s3_key)
            if not image_content:
                return {"error": "Image bytes not available from storage"}

            analysis = await self.llm_service.analyze_image_content(image_content, image.content_type)

            fi = analysis.get("food_items", [])
            is_food = analysis.get("is_food", False)
            conf = analysis.get("confidence", 0.0)
            image.is_food = is_food
            image.is_meal = infer_is_meal(is_food, conf, fi)
            image.analysis_description = analysis.get("description")
            image.food_items = fi
            image.estimated_calories = analysis.get("calories", 0)
            image.nutrients = analysis.get("nutrients", {})
            image.analysis_confidence = conf
            image.analysis_completed = datetime.now(timezone.utc)
            image.meal_name = _meal_name_from_analysis(analysis)

            self.db.images.save(image)
            self._sync_streak_safe(user_id)

            calories = analysis.get("calories", 0)
            exercise_recommendations = analysis.get(
                "exercise_recommendations",
                {"steps": int(calories * 20), "walking_km": round(calories / 50, 2)},
            )

            return {
                "success": True,
                "image_id": image.id,
                "analysis": {
                    "is_food": image.is_food,
                    "is_meal": image.is_meal,
                    "meal_name": image.meal_name,
                    "food_items": image.food_items,
                    "description": image.analysis_description,
                    "calories": image.estimated_calories,
                    "nutrients": image.nutrients,
                    "confidence": image.analysis_confidence,
                    "exercise_recommendations": exercise_recommendations,
                    "completed_at": image.analysis_completed.isoformat() if image.analysis_completed else None,
                },
            }

        except Exception as e:
            logger.exception("analyze_existing_image failed")
            return {"error": f"Analysis failed: {str(e)}"}

    def delete_image(self, image_id: str, user_id: str) -> Dict:
        try:
            image = self.db.images.get_by_id_and_owner(image_id, user_id)
            if not image:
                return {"error": "Image not found or access denied"}

            if not self.media_storage.delete_file(image.s3_key):
                return {"error": "Could not delete file from storage"}

            self.db.images.delete(image)
            self._sync_streak_safe(user_id)

            return {"success": True, "message": "Image deleted successfully"}

        except Exception as e:
            logger.exception("delete_image failed")
            return {"error": f"Delete failed: {str(e)}"}

    def get_image_with_analysis(self, image_id: str, user_id: str) -> Optional[Dict]:
        try:
            image = self.db.images.get_by_id_and_owner(image_id, user_id)
            if not image:
                return None
            return image.to_dict()
        except Exception as e:
            logger.exception("get_image_with_analysis failed")
            return None

    def get_user_images_with_analysis(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        filter_type: str = None,
        filter_value: str = None,
    ) -> List[Dict]:
        try:
            start, end = ImageRepository.parse_date_filter(filter_type, filter_value)
            images = self.db.images.list_by_owner(user_id, start=start, end=end)
            images = images[skip : skip + limit]

            now = datetime.now(timezone.utc)
            result = []
            for img in images:
                img_dict = img.to_dict()
                if img.presigned_url and img.presigned_url_expires_at and img.presigned_url_expires_at > now:
                    img_dict["file_url"] = img.presigned_url
                else:
                    presigned_url = self.media_storage.generate_presigned_url(img.s3_key, 86400)
                    if not presigned_url:
                        raise RuntimeError("Could not generate presigned URL")
                    img.presigned_url = presigned_url
                    img.presigned_url_expires_at = now + timedelta(seconds=86400)
                    img_dict["file_url"] = presigned_url
                    self.db.images.save(img)
                result.append(img_dict)
            return result
        except ValueError:
            raise
        except Exception as e:
            logger.exception("get_user_images failed")
            return []

    def get_image_with_presigned_url(
        self, image_id: str, user_id: str, expiration: int = 86400
    ) -> Optional[Dict]:
        try:
            image = self.db.images.get_by_id_and_owner(image_id, user_id)
            if not image:
                return None
            now = datetime.now(timezone.utc)
            if image.presigned_url and image.presigned_url_expires_at and image.presigned_url_expires_at > now:
                presigned_url = image.presigned_url
            else:
                presigned_url = self.media_storage.generate_presigned_url(image.s3_key, 86400)
                if not presigned_url:
                    return None
                image.presigned_url = presigned_url
                image.presigned_url_expires_at = now + timedelta(seconds=86400)
                self.db.images.save(image)
            image_data = image.to_dict()
            image_data["file_url"] = presigned_url
            return image_data
        except Exception as e:
            logger.exception("get_image_with_presigned_url failed")
            return None

    def get_suggested_meal_name(self, image_id: str, user_id: str) -> Optional[Dict]:
        image = self.db.images.get_by_id_and_owner(image_id, user_id)
        if not image:
            return None
        return {"meal_name": image.meal_name}

    def relog_image(self, image_id: str, user_id: str) -> Dict:
        src = self.db.images.get_by_id_and_owner(image_id, user_id)
        if not src:
            return {"error": "Image not found or access denied"}
        if not src.analysis_completed:
            return {"error": "Image has no completed analysis to relog"}
        now = datetime.now(timezone.utc)
        new_img = Image.new(
            filename=src.filename,
            original_filename=src.original_filename,
            file_url=src.file_url,
            s3_key=src.s3_key,
            s3_bucket=src.s3_bucket,
            file_size=src.file_size,
            content_type=src.content_type,
            description=src.description,
            tags=src.tags,
            owner_id=user_id,
            is_food=src.is_food,
            is_meal=src.is_meal,
            analysis_description=src.analysis_description,
            food_items=src.food_items,
            estimated_calories=src.estimated_calories,
            nutrients=src.nutrients,
            analysis_confidence=src.analysis_confidence,
            analysis_completed=now,
            meal_name=src.meal_name,
        )
        self.db.images.create(new_img)
        self._sync_streak_safe(user_id)
        return {"success": True, "image": new_img.to_dict()}

    async def test_storage_and_analysis(self, image_id: str, user_id: str) -> Dict:
        try:
            image = self.db.images.get_by_id_and_owner(image_id, user_id)
            if not image:
                return {"error": "Image not found"}

            results = {
                "image_info": {
                    "id": image.id,
                    "storage_key": image.s3_key,
                    "file_url": image.file_url,
                    "content_type": image.content_type,
                },
                "tests": {},
            }

            try:
                file_bytes = self.media_storage.get_file_content(image.s3_key)
                results["tests"]["file_read"] = {
                    "success": bool(file_bytes),
                    "content_size": len(file_bytes) if file_bytes else 0,
                }
            except Exception as e:
                results["tests"]["file_read"] = {"success": False, "error": str(e)}

            try:
                llm_test = await self.llm_service.test_api_connection()
                results["tests"]["llm_service"] = {"success": llm_test}
            except Exception as e:
                results["tests"]["llm_service"] = {"success": False, "error": str(e)}

            return results

        except Exception as e:
            logger.exception("test_storage_and_analysis failed")
            return {"error": f"Test failed: {str(e)}"}
