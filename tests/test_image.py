# test_image.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from app.utils.cloudinary import upload_image_cloudinary, delete_image_from_cloudinary
import cloudinary
import os
# import os

# Test configuration
@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables for Cloudinary"""
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "test_cloud")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "test_key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "test_secret")

@pytest.fixture
def sample_base64_image():
    """Returns a small valid base64 encoded image string"""
    return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z/C/HgAGgwJ/lK3Q6wAAAABJRU5ErkJggg=="

# Unit Tests
def test_configure_cloudinary(mock_env):
    """Test Cloudinary configuration loads env vars correctly"""
    from app.utils.cloudinary import configure_cloudinary
    configure_cloudinary()
    
    assert cloudinary.config().cloud_name == "test_cloud"
    assert cloudinary.config().api_key == "test_key"
    assert cloudinary.config().api_secret == "test_secret"

@pytest.mark.asyncio
@patch('cloudinary.uploader.upload')
async def test_upload_image_success(mock_upload, mock_env, sample_base64_image):
    """Test successful image upload"""
    mock_upload.return_value = {
        "public_id": "test_id",
        "secure_url": "https://test.url/image.jpg",
        "format": "jpg"
    }
    
    result = await upload_image_cloudinary(sample_base64_image)
    
    assert result["public_id"] == "test_id"
    assert result["url"] == "https://test.url/image.jpg"
    assert result["format"] == "jpg"
    mock_upload.assert_called_once()

@pytest.mark.asyncio
@patch('cloudinary.uploader.upload')
async def test_upload_image_failure(mock_upload, mock_env):
    """Test image upload failure"""
    mock_upload.side_effect = Exception("Upload failed")
    
    with pytest.raises(HTTPException) as exc_info:
        await upload_image_cloudinary("invalid_base64")
    
    assert exc_info.value.status_code == 500
    assert "Image upload failed" in str(exc_info.value.detail)

@pytest.mark.asyncio
@patch('cloudinary.uploader.destroy')
async def test_delete_image_success(mock_destroy, mock_env):
    """Test successful image deletion"""
    mock_destroy.return_value = {"result": "ok"}
    
    result = await delete_image_from_cloudinary("test_public_id")
    
    assert result is True
    mock_destroy.assert_called_once_with("test_public_id")

@pytest.mark.asyncio
@patch('cloudinary.uploader.destroy')
async def test_delete_image_failure(mock_destroy, mock_env):
    """Test image deletion failure"""
    mock_destroy.side_effect = Exception("Deletion failed")
    
    result = await delete_image_from_cloudinary("test_public_id")
    
    assert result is False

# Integration Test (requires actual Cloudinary credentials)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_upload_and_delete(sample_base64_image):
    """Integration test with real Cloudinary (requires .env)"""
    if not "CI":  # Skip if not in CI environment
        # Test upload
        upload_result = await upload_image_cloudinary(
            sample_base64_image,
            folder="test_uploads"
        )
        
        assert upload_result["url"] is not None
        assert upload_result["public_id"] is not None
        
        # Test deletion
        delete_result = await delete_image_from_cloudinary(
            upload_result["public_id"]
        )
        
        assert delete_result is True
    else:
        pytest.skip("Skipping integration test in CI environment")

# Test data cleanup
def pytest_sessionfinish(session, exitstatus):
    """Clean up any test resources after all tests run"""
    pass