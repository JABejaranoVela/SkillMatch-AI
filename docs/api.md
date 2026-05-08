# API Inicial

## Auth

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

## CVs

- `POST /api/v1/resumes/upload`
- `GET /api/v1/resumes`
- `GET /api/v1/resumes/{resume_id}`
- `POST /api/v1/resumes/{resume_id}/process`
- `GET /api/v1/resumes/{resume_id}/profile`

## Ofertas

- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs`
- `PUT /api/v1/jobs/{job_id}`
- `DELETE /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/import`
- `POST /api/v1/jobs/sync/external-api?search=python&limit=25`
- `POST /api/v1/jobs/sync/profile`
- `GET /api/v1/jobs/recommended`

## Matching

- `POST /api/v1/matching/resumes/{resume_id}`
- `GET /api/v1/matching/resumes/{resume_id}/results`
- `GET /api/v1/matching/results/{match_id}`

## Feedback

- `POST /api/v1/feedback`
- `GET /api/v1/feedback/me`
