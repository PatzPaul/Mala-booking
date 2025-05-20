# app/routers/services.py

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
# from sqlalchemy import select
from ..database import SessionLocal, engine
# from ..models import Service
from typing import Any
from .. import models, schemas
import logging
from ..utils.cache import get_cached_service, invalidate_services_cache, cache_services_response
from ..utils.cloudinary import upload_image_cloudinary, delete_image_from_cloudinary, extract_public_id


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/services",
    tags=["services"],
    responses={404: {"description": "Not found"}},
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=schemas.Service)
async def create_service(service: schemas.ServiceCreate, db: Session = Depends(get_db)) -> schemas.Service:
    """
    Create a new Service with Optional image upload 
    """

    service_data = service.model_dump(exclude={"image_base64"})

    # upload image if provided
    if service.image_base64:
        image_result = await upload_image_cloudinary(
            service.image_base64,
            folder="services/images"
        )
        service_data["image_url"] = image_result["url"]

    db_service = models.Service(**service_data)
    db.add(db_service)
    db.commit()
    db.refresh(db_service)
    await invalidate_services_cache()
    return db_service


@router.get("/", response_model=list[schemas.Service])
async def read_services(skip: int = 0,
                        limit: int = 100,
                        db: Session = Depends(get_db)
                        ) -> list[schemas.Service]:

    logger.info("Fetching services with pagination")
    """
    List all Services
    """

# Validate Pagination parameters
    if limit > 100:
        limit = 100
    if skip < 0:
        skip = 0

    cached_services = await get_cached_service(db)
    if cached_services:
        logger.info("Returning cached services")
        return cached_services[skip:skip + limit]

    query = (db.query(models.Service).offset(skip).limit(limit))

    results = query.all()

    if not results:
        logger.warning("No Services Found")
        raise HTTPException(status_code=404, detail="No Services Found")

    serialized_services = [
        schemas.Service(
            service_id=service.service_id,
            name=service.name,
            description=service.description,
            duration=service.duration,
            price=service.price,
            image_url=service.image_url,
            salon_id=service.salon_id,
            created_at=service.created_at,
            updated_at=service.updated_at,
        )
        for service in results
    ]

    await cache_services_response(serialized_services)

    return serialized_services


@router.get("/{service_id}", response_model=schemas.Service)
async def read_service(service_id: int, db: Session = Depends(get_db)) -> schemas.Service:
    """
    Get a specific Service with ID
    """
    service = db.query(models.Service).filter(
        models.Service.service_id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.put('/{service_id}', response_model=schemas.Service)
async def update_service(service_id: int, service_update: schemas.ServiceUpdate, db: Session = Depends(get_db)
                         ) -> schemas.Service:
    """
    Update a Service with comprehensive image handling 

    Features:
    - Update regular fields 
    - Upload new images 
    - Remove existing images 
    - Preserve existing images if no changes requested
    """
    db_service = db.query(models.Service).filter(
        models.Service.service_id == service_id).first()
    if not db_service:
        raise HTTPException(status_code=404, detail='Service was not found')

    for key, val in service_update.dict(exclude_none=True).items():
        setattr(db_service, key, val)

    update_data = service_update.dict(exclude_none=True, exclude={
        "image_base64", "remove_image"})

    # Handle image updates
    if service_update.remove_image and db_service.image_url:
        # Extract public_id from URL
        # public_id = db_service.image_url.split('/')[-1].split('.')[0]
        public_id = extract_public_id(db_service.image_url)
        if public_id and await delete_image_from_cloudinary(public_id):
            update_data["image_url"] = None
            logger.info(f"Deleted image for service {service_id}")

    if service_update.image_base64:
        result = await upload_image_cloudinary(service_update.image_base64, folder="services/images")
        update_data["image_url"] = result["url"]
        logger.info(f"Upload new image for service {service_id}")

# Update all fields
    for key, val in update_data.items():
        setattr(db_service, key, val)

    db.commit()
    db.refresh(db_service)
    await invalidate_services_cache()
    return db_service


@router.post("/upload-image/", response_model=schemas.ImageUploadResponse)
async def upload_service_image(
    upload_data: schemas.ImageUpload = Body(...),
    db: Session = Depends(get_db)
):
    """
    Upload an image to Cloudinary
    ---
    parameters:
      - in: body
        name: body
        description: Image upload data
        required: true
        schema:
          $ref: '#/definitions/ImageUpload'
    responses:
      200:
        description: Image uploaded successfully
        schema:
          $ref: '#/definitions/ImageUploadResponse'
      400:
        description: Invalid input
      500:
        description: Internal server error
    """
    try:
        if not upload_data.image_base64:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="image_base64 is required"
            )

        folder = "services/icons" if upload_data.is_icon else "services/images"

        # Upload to Cloudinary
        result = await upload_image_cloudinary(
            file_base64=upload_data.image_base64,
            folder=folder
        )

        logger.info(f"Image uploaded successfully to {result['url']}")

        return {
            "success": True,
            "url": result["url"],
            "public_id": result["public_id"]
        }

    except HTTPException as e:
        logger.error(f"Image upload failed: {str(e.detail)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during image upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )


@router.delete('/images/{public_id}', response_model=schemas.ImageDeleteResponse)
async def delete_cloudinary_image(
    public_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete an image from Cloudinary
    ---
    parameters:
      - name: public_id
        in: path
        required: true
        description: |
          The Cloudinary public ID to delete. Can be either:
          - Full public ID (e.g., 'services/images/abc123')
          - Just the identifier (e.g., 'abc123')
    """
    try:
        # Clean the public_id (remove URL parts if accidentally included)
        clean_public_id = extract_public_id(public_id) or public_id
        
        # Ensure we're not trying to delete with full URL
        if 'http' in clean_public_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide only the public_id, not full URL"
            )
        
        success = await delete_image_from_cloudinary(clean_public_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image {clean_public_id} not found or already deleted"
            )
            
        return {
            "success": True,
            "message": f"Image {clean_public_id} deleted successfully",
            "public_id": clean_public_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting image {public_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting image: {str(e)}"
        )

@router.delete('/{service_id}', response_model=schemas.ImageDeleteResponse)
async def delete_service(
    service_id: int, 
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """
    Delete a service and its associated images
    """
    db_service = db.query(models.Service).filter(
        models.Service.service_id == service_id
    ).first()
    if not db_service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Service not found'
        )

    # Delete associated images
    deletion_results = {}
    for asset_type in ['image_url']:
        if url := getattr(db_service, asset_type):
            public_id = extract_public_id(url)
            if public_id:
                deletion_results[asset_type] = await delete_image_from_cloudinary(public_id)

    # Delete the service record
    db.delete(db_service)
    db.commit()
    await invalidate_services_cache()

    # Prepare response
    deleted_assets = [k.replace('_url', '') for k, v in deletion_results.items() if v]
    message = (f"Service deleted successfully. "
               f"Deleted {len(deleted_assets)} associated assets: {', '.join(deleted_assets) or 'none'}")

    return {
        "success": True,
        "message": message,
        "public_id": None if not deletion_results else list(deletion_results.keys())[0]
    }