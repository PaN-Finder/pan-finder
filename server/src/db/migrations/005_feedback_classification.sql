ALTER TABLE feedback DROP CONSTRAINT feedback_feedback_type_check;
ALTER TABLE feedback ADD CONSTRAINT feedback_feedback_type_check CHECK (feedback_type IN ('Match', 'Relevant', 'Suggested', 'Not_Fit')) NOT VALID;
