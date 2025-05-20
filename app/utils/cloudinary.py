import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, status
import logging
from typing import Optional
import os


logger = logging.getLogger(__name__)


def configure_cloudinary():
    """
    Configure Cloudinary with Environment variables
    """
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True
    )


async def upload_image_cloudinary(
    file_base64: str,
    folder: str = "services",
    public_id: Optional[str] = None
) -> dict:
    try:
        configure_cloudinary()

        # Remove data URL prefix if present
        if file_base64.startswith("data:"):
            file_base64 = file_base64.split(",", 1)[1]

        upload_result = cloudinary.uploader.upload(
            file=f"data:image/png;base64,{file_base64}",
            folder=folder,
            public_id=public_id,
            overwrite=True,
            invalidate=True
        )

        return {
            "public_id": upload_result["public_id"],
            "url": upload_result["secure_url"],
            "format": upload_result["format"]
        }
    except Exception as e:
        logger.error(f"Cloudinary upload error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image upload failed: {str(e)}"
        )


async def delete_image_from_cloudinary(public_id: str) -> bool:
    """
    Delete an image from Cloudinary


    Args:
        public_id: Cloudinary Public ID of the Image to delete

    Returns:
        bool: True if deletion was succesful 
    """

    try:
        configure_cloudinary()
        result = cloudinary.uploader.destroy(public_id)
        if result.get('result') == 'ok':
            logger.info(f"Succesfully deleted image: {public_id}")
            return True
        logger.warning(f"Failed to delete image: {result}")
        return False
    except Exception as e:
        logger.error(
            f"Error deleting image {public_id}from Cloudinary: {str(e)}")
        return False


def extract_public_id(url: str) -> Optional[str]:
    """
    Extract Cloudinary public ID from URL with proper formatting
    Handles these formats:
    - https://res.cloudinary.com/demo/image/upload/v1234567/sample.jpg
    - https://res.cloudinary.com/demo/image/upload/sample.jpg
    - sample.jpg (when public_id is passed directly)
    """
    if not url:
        return None
    
    # If it's already a public_id (no URL structure)
    if 'res.cloudinary.com' not in url:
        return url.split('.')[0]
    
    try:
        parts = url.split('/')
        upload_index = parts.index('upload')
        
        # The public_id starts after 'upload' or version
        public_id_parts = parts[upload_index + 1:]
        
        # Remove version if present (v1234567)
        if public_id_parts[0].startswith('v'):
            public_id_parts = public_id_parts[1:]
            
        public_id = '/'.join(public_id_parts)
        
        # Remove file extension
        return public_id.split('.')[0]
    except Exception as e:
        logger.warning(f"Could not extract public_id from {url}: {str(e)}")
        return None