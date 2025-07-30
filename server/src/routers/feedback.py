from fastapi import APIRouter, HTTPException
from pydantic import Field, BaseModel

from ..setup_logging import get_logger
from ..models.feedback import Feedback
from ..models.feedback_repository import FeedbackRepository
from ..models.statistic_repository import StatisticRepository

logger = get_logger(__name__)

router = APIRouter(prefix="/feedback")


class FeedbackRequest(BaseModel):
    statistic_id: str = Field(
        ..., description="ID of the statistic to which feedback is related"
    )
    feedback_type: str = Field(
        ...,
        description="Type of feedback: 'positive' or 'negative'",
        pattern=r"^(positive|negative)$",
    )
    doi: str = Field(..., description="DOI to which the feedback is related")


@router.post("/submit")
def submit_feedback(feedback_request: FeedbackRequest) -> dict:
    """
    Submit feedback for a statistic.
    Returns: id, statistic_id, feedback_type, metadata, created_at
    """
    try:
        logger.info(
            f"Submitting feedback for statistic ID: {feedback_request.statistic_id}"
        )

        # Fetch statistic row to ensure it exists
        statistic = StatisticRepository.select_by_id(feedback_request.statistic_id)

        if not statistic:
            logger.error(
                f"Statistic with ID {feedback_request.statistic_id} not found."
            )
            raise HTTPException(status_code=404, detail="Statistic not found.")

        # Check if doi is in the statistic's result data (to prevent invalid feedback)
        if feedback_request.doi not in [
            result.get("doi") for result in statistic.results
        ]:
            logger.error(
                f"DOI {feedback_request.doi} not found in statistic results for ID {feedback_request.statistic_id}."
            )
            raise HTTPException(
                status_code=400, detail="DOI not found in statistic results."
            )

        feedback = Feedback(
            statistic_id=feedback_request.statistic_id,
            feedback_type=feedback_request.feedback_type,
            metadata={"doi": feedback_request.doi},
        )
        feedback_id = FeedbackRepository.insert(feedback)
        logger.info(f"Feedback submitted successfully with ID: {feedback_id}")
        return feedback.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error submitting feedback for statistic ID {feedback_request.statistic_id}: {e}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to submit feedback: {str(e)}"
        )
