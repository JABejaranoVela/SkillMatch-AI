import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { Job } from '../jobs/job.service';

export type InteractionType = 'viewed' | 'saved' | 'discarded' | 'applied';

export interface FeedbackJob {
  id: number;
  job_id: number;
  match_result_id: number | null;
  interaction_type: InteractionType;
  created_at: string;
  job: Job;
  final_score: number;
  matching_skills: string[];
  missing_skills: string[];
}

@Injectable({ providedIn: 'root' })
export class FeedbackService {
  constructor(
    private readonly http: HttpClient,
    private readonly api: ApiService
  ) {}

  create(jobId: number, interactionType: InteractionType, matchResultId?: number): Observable<unknown> {
    return this.http.post(`${this.api.baseUrl}/feedback`, {
      job_id: jobId,
      match_result_id: matchResultId ?? null,
      interaction_type: interactionType
    });
  }

  listJobs(interactionType?: InteractionType): Observable<FeedbackJob[]> {
    const query = interactionType ? `?interaction_type=${interactionType}` : '';
    return this.http.get<FeedbackJob[]>(`${this.api.baseUrl}/feedback/me/jobs${query}`);
  }
}
