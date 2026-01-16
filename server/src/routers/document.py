import json

from fastapi import APIRouter, Header, HTTPException, Path
from pydantic import BaseModel, JsonValue

from ..db.models.document_repository import DocumentRepository
from ..routers.session import verify_session
from ..utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/document")


class DocumentDetailsResponseModel(BaseModel):
    id: int
    doi: str
    title: str
    abstract: str | None
    facility_name: str | None


@router.get("/raw/{doi:path}")
async def get_raw_document(
    doi: str = Path(..., min_length=1, description="Document DOI"),
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
) -> JsonValue:
    """Get raw json document by DOI. Returns parsed JSON when possible, otherwise the raw string."""
    verify_session(x_session_id)

    try:
        logger.info(f"Fetching raw document for DOI: {doi}")
        document = DocumentRepository.get_by_doi(doi)
        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document with DOI '{doi}' not found"
            )
        logger.info(f"Successfully fetched raw document for DOI: {doi}")
        raw = document.raw or ""
        try:
            # Try to parse stored raw JSON
            return json.loads(raw)
        except Exception:
            # If parsing fails, return the raw string so callers still get the data
            return raw
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching raw document for DOI {doi}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch raw document: {str(e)}"
        ) from e


@router.get("/{doi:path}")
async def get_document_details(
    doi: str = Path(..., min_length=1, description="Document DOI"),
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
) -> DocumentDetailsResponseModel:
    """
    Get detailed document information by DOI.
    Returns: id, doi, title, text, facility_name
    """
    verify_session(x_session_id)

    try:
        logger.info(f"Fetching document details for DOI: {doi}")
        document = DocumentRepository.get_by_doi(doi)
        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document with DOI '{doi}' not found"
            )
        logger.info(f"Successfully fetched document details for DOI: {doi}")

        return DocumentDetailsResponseModel(**document.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching document details for DOI {doi}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch document details: {str(e)}"
        ) from e
