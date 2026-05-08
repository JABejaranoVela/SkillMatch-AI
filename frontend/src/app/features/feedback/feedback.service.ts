import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '../../core/api.service';

export type InteractionType = 'viewed' | 'saved' | 'discarded' | 'applied';

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
}

