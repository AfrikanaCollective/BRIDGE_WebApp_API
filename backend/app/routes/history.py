# backend/app/routes/history.py
import logging
from fastapi import APIRouter, HTTPException, Query
from app.clients.mongo_client import MongoClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/history", tags=["history"])

mongo_client: MongoClient = None


@router.get("/responses")
async def get_all_responses(
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100)
):
    """
    Get all form responses with pagination
    """
    try:
        responses = await mongo_client.get_all_responses(skip=skip, limit=limit)
        total = await mongo_client.get_response_count()

        # Convert ObjectId to string
        for response in responses:
            if "_id" in response:
                response["_id"] = str(response["_id"])

        return {
            "success": True,
            "data": responses,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total
            }
        }
    except Exception as e:
        logger.error(f"Get responses error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/responses/{response_id}")
async def get_response(response_id: str):
    """
    Get specific response by ID
    """
    try:
        response = await mongo_client.get_response(response_id)

        if not response:
            raise HTTPException(status_code=404, detail="Response not found")

        response["_id"] = str(response["_id"])

        return {
            "success": True,
            "data": response
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get response error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/responses/filename/{filename}")
async def get_responses_by_filename(filename: str, limit: int = Query(10, ge=1, le=50)):
    """
    Get responses by filename
    """
    try:
        responses = await mongo_client.get_responses_by_filename(filename, limit=limit)

        for response in responses:
            if "_id" in response:
                response["_id"] = str(response["_id"])

        return {
            "success": True,
            "data": responses,
            "count": len(responses)
        }
    except Exception as e:
        logger.error(f"Get responses by filename error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/responses/{response_id}")
async def delete_response(response_id: str):
    """
    Delete response
    """
    try:
        success = await mongo_client.delete_response(response_id)

        if not success:
            raise HTTPException(status_code=404, detail="Response not found")

        return {
            "success": True,
            "message": "Response deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete response error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
