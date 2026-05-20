ALTER TABLE feedback DROP CONSTRAINT feedback_feedback_type_check;

UPDATE feedback
SET feedback_type = 'Not_Relevant'
WHERE feedback_type = 'Not_Fit';

ALTER TABLE feedback ADD CONSTRAINT feedback_feedback_type_check CHECK (feedback_type IN ('Match', 'Relevant', 'Suggested', 'Not_Relevant')) NOT VALID;