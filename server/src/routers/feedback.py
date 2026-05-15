from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..db.models.feedback import Feedback
from ..db.models.feedback_repository import FeedbackRepository
from ..db.models.statistic_repository import StatisticRepository
from ..routers.session import verify_session
from ..utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/feedback")


class FeedbackRequest(BaseModel):
    statistic_id: str = Field(
        ..., description="ID of the statistic to which feedback is related"
    )
    feedback_type: str = Field(
        ...,
        description="Classification: 'Match', 'Relevant', 'Suggested', or 'Not_Fit'",
        pattern=r"^(Match|Relevant|Suggested|Not_Fit)$",
    )
    doi: str = Field(..., description="DOI to which the feedback is related")


@router.post("/submit")
def submit_feedback(
    feedback_request: FeedbackRequest,
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
) -> dict:
    """
    Submit feedback for a statistic.
    Returns: id, statistic_id, feedback_type, metadata, created_at
    """
    verify_session(x_session_id)

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
        if statistic.results is None:
            all_results = []
        else:
            all_results = list(statistic.results.relevant) + list(
                statistic.results.weakly_relevant
            )

        if feedback_request.doi not in [
            (
                result.model_dump().get("doi")
                if hasattr(result, "model_dump")
                else getattr(result, "doi", None)
            )
            for result in all_results
        ]:
            logger.error(
                f"DOI {feedback_request.doi} not found in statistic results for ID {feedback_request.statistic_id}."
            )
            raise HTTPException(
                status_code=400, detail="DOI not found in statistic results."
            )

        # Fetch feedback table to see if feedback already exists
        existing_feedback = FeedbackRepository.select_by_statistic_id_and_metadata(
            feedback_request.statistic_id, {"doi": feedback_request.doi}
        )

        if existing_feedback and existing_feedback.id is not None:
            existing_feedback.feedback_type = feedback_request.feedback_type
            updated_feedback = FeedbackRepository.update_feedback_type(
                existing_feedback.id, feedback_request.feedback_type
            )
            if not updated_feedback:
                logger.error(
                    f"Failed to update feedback for ID {existing_feedback.id}."
                )
                raise HTTPException(
                    status_code=500, detail="Failed to update feedback."
                )

            return updated_feedback.to_dict()

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
        ) from e
