from fastapi import APIRouter, HTTPException, Path
from ..models.document_repository import DocumentRepository
from ..setup_logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/document")


@router.get("/{doi:path}")
async def get_document_details(
    doi: str = Path(..., min_length=1, description="Document DOI")
) -> dict:
    """
    Get detailed document information by DOI.
    Returns: id, doi, title, text, summary, raw, facility_name
    """
    try:
        logger.info(f"Fetching document details for DOI: {doi}")
        document = DocumentRepository.get_by_doi(doi)
        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document with DOI '{doi}' not found"
            )
        logger.info(f"Successfully fetched document details for DOI: {doi}")
        return document.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching document details for DOI {doi}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch document details: {str(e)}"
        )
