import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '../../core/api.service';

export interface Job {
  id: number;
  title: string;
  company: string | null;
  description: string;
  requirements: string | null;
  location: string | null;
  modality: string | null;
  source: string;
  external_id: string | null;
  url: string | null;
  status: string;
}

export interface JobRecommendation {
  job: Job;
  final_score: number;
  rules_score: number;
  semantic_score: number;
  matching_skills: string[];
  missing_skills: string[];
  score_breakdown?: {
    rules_weight: number;
    semantic_weight: number;
    rules_score: number;
    semantic_score: number;
  };
}

export interface ProfileSyncResult {
  profile_type: string | null;
  search_terms: string[];
  sources: Array<{
    source: string;
    imported: number;
    updated?: number;
    skipped: number;
    attribution: string;
  }>;
}

@Injectable({ providedIn: 'root' })
export class JobService {
  constructor(
    private readonly http: HttpClient,
    private readonly api: ApiService
  ) {}

  list(): Observable<Job[]> {
    return this.http.get<Job[]>(`${this.api.baseUrl}/jobs`);
  }

  recommended(): Observable<JobRecommendation[]> {
    return this.http.get<JobRecommendation[]>(`${this.api.baseUrl}/jobs/recommended`);
  }

  syncForProfile(): Observable<ProfileSyncResult> {
    return this.http.post<ProfileSyncResult>(`${this.api.baseUrl}/jobs/sync/profile`, {});
  }

  import(file: File): Observable<unknown> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post(`${this.api.baseUrl}/jobs/import`, formData);
  }
}
