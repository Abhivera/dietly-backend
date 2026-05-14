from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.meal_rules import infer_is_meal
from app.models.image import Image
from app.services.llm_service import LLMService
from app.services.s3_service import S3Service
from app.services.streak_service import sync_user_streak
import logging
from io import BytesIO
import re

logger = logging.getLogger(__name__)


def _meal_name_from_analysis(analysis: Dict) -> Optional[str]:
    raw = analysis.get("meal_name")
    if raw is None:
        return None
    s = str(raw).strip()[:255]
    return s or None


class ImageService:
    def __init__(self, db: Session):
        self.db = db
        self.llm_service = LLMService()
        self.s3_service = S3Service()

    def _sync_streak_safe(self, user_id: int) -> None:
        try:
            sync_user_streak(self.db, user_id)
        except Exception:
            logger.exception("sync_user_streak failed for user_id=%s", user_id)

    async def upload_and_analyze_image(self, file_obj, user_id: int, original_filename: str, file_size: int, content_type: str, user_description: str = None) -> Dict:
        """Upload image to S3 and analyze it using content from memory. Optionally use user description."""
        try:
            # Reset file pointer to beginning
            file_obj.seek(0)
            
            # Read content for analysis before upload
            image_content = file_obj.read()
            
            # Reset file pointer for S3 upload
            file_obj.seek(0)
            
            # Upload to S3
            upload_result = self.s3_service.upload_file(file_obj, user_id, original_filename)

            if not upload_result['success']:
                return {"error": upload_result['error']}

            # Create image record in database
            image = Image(
                filename=upload_result['filename'],
                original_filename=upload_result['original_filename'],
                file_url=upload_result['file_url'],
                s3_key=upload_result['s3_key'],
                s3_bucket=upload_result['bucket'],
                file_size=file_size,
                content_type=content_type,
                owner_id=user_id
            )

            self.db.add(image)
            self.db.commit()
            self.db.refresh(image)

            # Analyze using image content from memory instead of S3 URL
            analysis = await self.llm_service.analyze_image_content(
                image_content, content_type, description=user_description
            )
            logger.debug("Analysis result keys: %s", list(analysis.keys()))

            calories = analysis.get('calories', 0)
            exercise_recommendations = analysis.get(
                'exercise_recommendations',
                {"steps": int(calories * 20), "walking_km": round(calories / 50, 2)}
            )

            # Update image with analysis results
            image.is_food = analysis.get('is_food', False)
            image.is_meal = infer_is_meal(
                image.is_food,
                analysis.get('confidence', 0.0),
                analysis.get('food_items', []),
            )
            image.analysis_description = analysis.get('description')
            image.food_items = analysis.get('food_items', [])
            image.estimated_calories = calories
            image.nutrients = analysis.get('nutrients', {})
            image.analysis_confidence = analysis.get('confidence', 0.0)
            image.analysis_completed = datetime.now(timezone.utc)
            image.meal_name = _meal_name_from_analysis(analysis)
            image.description = analysis.get('description')  # Set top-level description

            self.db.commit()
            self.db.refresh(image)

            self._sync_streak_safe(user_id)

            # Patch the image dict's analysis to match the top-level one
            image_dict = image.to_dict()
            if 'analysis' in image_dict:
                image_dict['analysis']['exercise_recommendations'] = exercise_recommendations

            return {
                "success": True,
                "image": image_dict
            }

        except Exception as e:
            logger.exception("upload_and_analyze_image failed")
            self.db.rollback()
            return {"error": f"Upload and analysis failed: {str(e)}"}

    async def upload_image_only(self, file_obj, original_filename: str, file_size: int, content_type: str, user_id: int) -> Dict:
        """Upload image to S3 without analysis"""
        try:
            file_obj.seek(0)
            upload_result = self.s3_service.upload_file(file_obj, user_id, original_filename)

            if not upload_result['success']:
                return {"error": upload_result['error']}

            image = Image(
                filename=upload_result['filename'],
                original_filename=upload_result['original_filename'],
                file_url=upload_result['file_url'],
                s3_key=upload_result['s3_key'],
                s3_bucket=upload_result['bucket'],
                file_size=file_size,
                content_type=content_type,
                owner_id=user_id
            )

            self.db.add(image)
            self.db.commit()
            self.db.refresh(image)

            return {
                "success": True,
                "image": image.to_dict()
            }

        except Exception as e:
            logger.exception("upload_image_only failed")
            self.db.rollback()
            return {"error": f"Upload failed: {str(e)}"}

    async def upload_image_with_analysis(self, file_obj, original_filename: str, file_size: int, content_type: str, user_id: int, analysis: Dict) -> Dict:
        """Upload image to S3 with pre-computed analysis"""
        try:
            file_obj.seek(0)
            upload_result = self.s3_service.upload_file(file_obj, user_id, original_filename)

            if not upload_result['success']:
                return {"error": upload_result['error']}

            fi = analysis.get('food_items', [])
            is_food = analysis.get('is_food', False)
            conf = analysis.get('confidence', 0.0)
            image = Image(
                filename=upload_result['filename'],
                original_filename=upload_result['original_filename'],
                file_url=upload_result['file_url'],
                s3_key=upload_result['s3_key'],
                s3_bucket=upload_result['bucket'],
                file_size=file_size,
                content_type=content_type,
                owner_id=user_id,
                # Set analysis data immediately
                is_food=is_food,
                is_meal=infer_is_meal(is_food, conf, fi),
                analysis_description=analysis.get('description'),
                food_items=fi,
                estimated_calories=analysis.get('calories', 0),
                nutrients=analysis.get('nutrients', {}),
                analysis_confidence=conf,
                analysis_completed=datetime.now(timezone.utc),
                meal_name=_meal_name_from_analysis(analysis),
            )

            self.db.add(image)
            self.db.commit()
            self.db.refresh(image)

            self._sync_streak_safe(user_id)

            return {
                "success": True,
                "image": image.to_dict()
            }

        except Exception as e:
            logger.exception("upload_image_with_analysis failed")
            self.db.rollback()
            return {"error": f"Upload failed: {str(e)}"}

    async def update_image_analysis(self, image_id: int, analysis: Dict) -> Dict:
        """Update existing image with analysis results"""
        try:
            image = self.db.query(Image).filter(Image.id == image_id).first()
            
            if not image:
                return {"error": "Image not found"}

            fi = analysis.get('food_items', [])
            is_food = analysis.get('is_food', False)
            conf = analysis.get('confidence', 0.0)
            image.is_food = is_food
            image.is_meal = infer_is_meal(is_food, conf, fi)
            image.analysis_description = analysis.get('description')
            image.food_items = fi
            image.estimated_calories = analysis.get('calories', 0)
            image.nutrients = analysis.get('nutrients', {})
            image.analysis_confidence = conf
            image.analysis_completed = datetime.now(timezone.utc)
            if "meal_name" in analysis:
                image.meal_name = _meal_name_from_analysis(analysis)

            self.db.commit()
            self.db.refresh(image)

            self._sync_streak_safe(image.owner_id)

            return {
                "success": True,
                "image": image.to_dict()
            }

        except Exception as e:
            logger.exception("update_image_analysis failed")
            self.db.rollback()
            return {"error": f"Update failed: {str(e)}"}

    async def analyze_existing_image(self, image_id: int, user_id: int) -> Dict:
        """Re-analyze an image using bytes loaded from S3 only."""
        try:
            image = self.db.query(Image).filter(
                Image.id == image_id,
                Image.owner_id == user_id
            ).first()

            if not image:
                return {"error": "Image not found or access denied"}

            image_content = self.s3_service.get_file_content(image.s3_key)
            if not image_content:
                return {"error": "Image bytes not available from object storage"}

            analysis = await self.llm_service.analyze_image_content(image_content, image.content_type)

            fi = analysis.get('food_items', [])
            is_food = analysis.get('is_food', False)
            conf = analysis.get('confidence', 0.0)
            image.is_food = is_food
            image.is_meal = infer_is_meal(is_food, conf, fi)
            image.analysis_description = analysis.get('description')
            image.food_items = fi
            image.estimated_calories = analysis.get('calories', 0)
            image.nutrients = analysis.get('nutrients', {})
            image.analysis_confidence = conf
            image.analysis_completed = datetime.now(timezone.utc)
            image.meal_name = _meal_name_from_analysis(analysis)

            self.db.commit()
            self.db.refresh(image)

            self._sync_streak_safe(user_id)

            calories = analysis.get('calories', 0)
            exercise_recommendations = analysis.get(
                'exercise_recommendations',
                {"steps": int(calories * 20), "walking_km": round(calories / 50, 2)}
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
                    "completed_at": image.analysis_completed.isoformat() if image.analysis_completed else None
                }
            }

        except Exception as e:
            logger.exception("analyze_existing_image failed")
            self.db.rollback()
            return {"error": f"Analysis failed: {str(e)}"}

    def delete_image(self, image_id: int, user_id: int) -> Dict:
        """Delete image and remove from S3"""
        try:
            image = self.db.query(Image).filter(
                Image.id == image_id,
                Image.owner_id == user_id
            ).first()

            if not image:
                return {"error": "Image not found or access denied"}

            if not self.s3_service.delete_file(image.s3_key):
                return {"error": "Could not delete file from object storage"}

            self.db.delete(image)
            self.db.commit()

            self._sync_streak_safe(user_id)

            return {"success": True, "message": "Image deleted successfully"}

        except Exception as e:
            logger.exception("delete_image failed")
            self.db.rollback()
            return {"error": f"Delete failed: {str(e)}"}

    def get_image_with_analysis(self, image_id: int, user_id: int) -> Optional[Dict]:
        """Get image with its analysis data"""
        try:
            image = self.db.query(Image).filter(
                Image.id == image_id,
                Image.owner_id == user_id
            ).first()
            if not image:
                return None
            image_dict = image.to_dict()
            return image_dict
        except Exception as e:
            logger.exception("get_image_with_analysis failed")
            return None

    def get_user_images_with_analysis(self, user_id: int, skip: int = 0, limit: int = 20, filter_type: str = None, filter_value: str = None) -> List[Dict]:
        """List user images with optional presigned URLs. Filters: date=YYYY-MM-DD, week=YYYY-Www, month=YYYY-MM."""
        try:
            query = self.db.query(Image).filter(Image.owner_id == user_id)
            if filter_type and not filter_value:
                raise ValueError("filter_value is required when filter_type is set")
            if filter_type == "date" and filter_value:
                try:
                    date_obj = datetime.strptime(filter_value, "%Y-%m-%d")
                except ValueError as e:
                    raise ValueError("Invalid date filter; use YYYY-MM-DD") from e
                next_day = date_obj + timedelta(days=1)
                query = query.filter(Image.created_at >= date_obj, Image.created_at < next_day)
            elif filter_type == "week" and filter_value:
                match = re.match(r"(\d{4})-W(\d{2})", filter_value)
                if not match:
                    raise ValueError("Invalid week filter; use YYYY-Www (ISO week)")
                try:
                    year, week = int(match.group(1)), int(match.group(2))
                    date_obj = datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w")
                    next_week = date_obj + timedelta(weeks=1)
                    query = query.filter(Image.created_at >= date_obj, Image.created_at < next_week)
                except ValueError as e:
                    raise ValueError("Invalid week filter value") from e
            elif filter_type == "month" and filter_value:
                try:
                    date_obj = datetime.strptime(filter_value, "%Y-%m")
                except ValueError as e:
                    raise ValueError("Invalid month filter; use YYYY-MM") from e
                if date_obj.month == 12:
                    next_month = date_obj.replace(year=date_obj.year + 1, month=1)
                else:
                    next_month = date_obj.replace(month=date_obj.month + 1)
                query = query.filter(Image.created_at >= date_obj, Image.created_at < next_month)
            elif filter_type:
                raise ValueError("filter_type must be date, week, or month")

            images = query.offset(skip).limit(limit).all()
            now = datetime.now(timezone.utc)
            result = []
            for img in images:
                img_dict = img.to_dict()
                if img.presigned_url and img.presigned_url_expires_at and img.presigned_url_expires_at > now:
                    img_dict['file_url'] = img.presigned_url
                else:
                    presigned_url = self.s3_service.generate_presigned_url(img.s3_key, 86400)
                    if not presigned_url:
                        raise RuntimeError("Could not generate presigned URL")
                    img.presigned_url = presigned_url
                    img.presigned_url_expires_at = now + timedelta(seconds=86400)
                    self.db.commit()
                    img_dict['file_url'] = presigned_url
                result.append(img_dict)
            return result
        except ValueError:
            raise
        except Exception as e:
            logger.exception("get_user_images failed")
            return []

    def get_image_with_presigned_url(self, image_id: int, user_id: int, expiration: int = 86400) -> Optional[Dict]:
        """Get image details with a presigned URL valid for 1 day, only refreshed once per day."""
        try:
            image = self.db.query(Image).filter(
                Image.id == image_id,
                Image.owner_id == user_id
            ).first()
            if not image:
                return None
            now = datetime.now(timezone.utc)
            if image.presigned_url and image.presigned_url_expires_at and image.presigned_url_expires_at > now:
                presigned_url = image.presigned_url
            else:
                presigned_url = self.s3_service.generate_presigned_url(image.s3_key, 86400)
                if not presigned_url:
                    return None
                image.presigned_url = presigned_url
                image.presigned_url_expires_at = now + timedelta(seconds=86400)
                self.db.commit()
            image_data = image.to_dict()
            image_data['file_url'] = presigned_url
            return image_data
        except Exception as e:
            logger.exception("get_image_with_presigned_url failed")
            return None

    def get_suggested_meal_name(self, image_id: int, user_id: int) -> Optional[Dict]:
        """Return persisted LLM meal title for an image (no extra model call)."""
        image = (
            self.db.query(Image)
            .filter(Image.id == image_id, Image.owner_id == user_id)
            .first()
        )
        if not image:
            return None
        return {"meal_name": image.meal_name}

    def relog_image(self, image_id: int, user_id: int) -> Dict:
        """New image row pointing at the same object; copies analysis for 'log again' with a fresh timestamp."""
        src = (
            self.db.query(Image)
            .filter(Image.id == image_id, Image.owner_id == user_id)
            .first()
        )
        if not src:
            return {"error": "Image not found or access denied"}
        if not src.analysis_completed:
            return {"error": "Image has no completed analysis to relog"}
        now = datetime.now(timezone.utc)
        new_img = Image(
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
            presigned_url=None,
            presigned_url_expires_at=None,
        )
        self.db.add(new_img)
        self.db.commit()
        self.db.refresh(new_img)
        self._sync_streak_safe(user_id)
        return {"success": True, "image": new_img.to_dict()}

    async def test_s3_and_analysis(self, image_id: int, user_id: int) -> Dict:
        try:
            image = self.db.query(Image).filter(
                Image.id == image_id,
                Image.owner_id == user_id
            ).first()

            if not image:
                return {"error": "Image not found"}

            results = {
                "image_info": {
                    "id": image.id,
                    "s3_key": image.s3_key,
                    "file_url": image.file_url,
                    "content_type": image.content_type
                },
                "tests": {}
            }

            try:
                s3_content = self.s3_service.get_file_content(image.s3_key)
                results["tests"]["s3_content_access"] = {
                    "success": bool(s3_content),
                    "content_size": len(s3_content) if s3_content else 0
                }
            except Exception as e:
                results["tests"]["s3_content_access"] = {
                    "success": False,
                    "error": str(e)
                }

            try:
                llm_test = await self.llm_service.test_api_connection()
                results["tests"]["llm_service"] = {
                    "success": llm_test
                }
            except Exception as e:
                results["tests"]["llm_service"] = {
                    "success": False,
                    "error": str(e)
                }

            return results

        except Exception as e:
            logger.exception("test_s3_and_analysis failed")
            return {"error": f"Test failed: {str(e)}"}