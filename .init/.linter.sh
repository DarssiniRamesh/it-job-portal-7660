#!/bin/bash
cd /home/kavia/workspace/code-generation/it-job-portal-7660/job_portal_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

