import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '../../core/api.service';

export interface MatchResult {
  id: number;
  job_id: number;
  rules_score: number;
  semantic_score: number;
  final_score: number;
  explanation: {
    matching_skills?: string[];
    missing_skills?: string[];
    positive_signals?: string[];
    penalties?: string[];
    score_breakdown?: {
      rules_weight: number;
      semantic_weight: number;
      rules_score: number;
      semantic_score: number;
    };
  };
  algorithm_version: string;
  job: {
    id: number;
    title: string;
    company: string | null;
    source: string;
    url: string | null;
  } | null;
}

@Injectable({ providedIn: 'root' })
export class MatchingService {
  constructor(
    private readonly http: HttpClient,
    private readonly api: ApiService
  ) {}

  run(resumeId: number): Observable<MatchResult[]> {
    return this.http.post<MatchResult[]>(`${this.api.baseUrl}/matching/resumes/${resumeId}`, {});
  }

  runActive(): Observable<MatchResult[]> {
    return this.http.post<MatchResult[]>(`${this.api.baseUrl}/matching/active`, {});
  }
}
