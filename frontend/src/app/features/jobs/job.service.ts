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
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  contract_type: string | null;
  published_at: string | null;
  source: string;
  external_id: string | null;
  url: string | null;
  status: string;
  created_at: string;
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

export interface JobRecommendationPage {
  items: JobRecommendation[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface JobSourceResult {
  source: string;
  imported: number;
  updated?: number;
  skipped: number;
  attribution: string;
}

export interface JobSearchTask {
  task_id: string;
  status: 'pending' | 'searching' | 'importing' | 'ranking' | 'completed' | 'failed';
  message: string;
  sources: {
    items?: JobSourceResult[];
    search_terms?: string[];
  } | null;
  imported: number;
  updated: number;
  skipped: number;
  error: string | null;
}

@Injectable({ providedIn: 'root' })
export class JobService {
  private readonly recommendationsTtlMs = 10 * 60 * 1000;
  private recommendationsCache: {
    items: JobRecommendation[];
    total: number;
    loadedAt: number;
  } | null = null;

  constructor(
    private readonly http: HttpClient,
    private readonly api: ApiService
  ) {}

  list(): Observable<Job[]> {
    return this.http.get<Job[]>(`${this.api.baseUrl}/jobs`);
  }

  recommended(limit = 20, offset = 0): Observable<JobRecommendationPage> {
    return this.http.get<JobRecommendationPage>(
      `${this.api.baseUrl}/jobs/recommended`,
      { params: { limit, offset } }
    );
  }

  startProfileSearch(): Observable<JobSearchTask> {
    this.clearRecommendedCache();
    return this.http.post<JobSearchTask>(`${this.api.baseUrl}/jobs/search/profile`, {});
  }

  searchStatus(taskId: string): Observable<JobSearchTask> {
    return this.http.get<JobSearchTask>(`${this.api.baseUrl}/jobs/search/${taskId}`);
  }

  import(file: File): Observable<unknown> {
    const formData = new FormData();
    formData.append('file', file);
    this.clearRecommendedCache();
    return this.http.post(`${this.api.baseUrl}/jobs/import`, formData);
  }

  getCachedRecommendations(): { items: JobRecommendation[]; total: number } | null {
    if (!this.recommendationsCache) {
      return null;
    }
    const isFresh = Date.now() - this.recommendationsCache.loadedAt < this.recommendationsTtlMs;
    return isFresh
      ? {
          items: this.recommendationsCache.items,
          total: this.recommendationsCache.total
        }
      : null;
  }

  setRecommendedCache(items: JobRecommendation[], total: number): void {
    this.recommendationsCache = {
      items,
      total,
      loadedAt: Date.now()
    };
  }

  clearRecommendedCache(): void {
    this.recommendationsCache = null;
  }
}
