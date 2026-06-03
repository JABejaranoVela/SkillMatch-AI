import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '../../core/api.service';

export interface Resume {
  id: number;
  filename: string;
  file_type: string;
  status: string;
  is_active: boolean;
  created_at: string;
  processed_at: string | null;
}

export interface ProfileScore {
  name: string;
  score: number;
  raw_score?: number;
  matched_skills: string[];
  matched_signals: string[];
}

export interface ProfileAnalysis {
  primary_profile: ProfileScore | null;
  secondary_profile: ProfileScore | null;
  profile_scores: ProfileScore[];
  skill_categories: Record<string, string[]>;
  skill_sources: {
    dictionary: number;
    ner: number;
    pattern: number;
    total: number;
  };
}

export interface ProfessionalProfile {
  id: number;
  profile_type: string | null;
  summary: string | null;
  experience_years: number | null;
  education: Record<string, unknown> | null;
  languages: string[] | null;
  technologies: string[] | null;
  analysis: ProfileAnalysis | null;
}

@Injectable({ providedIn: 'root' })
export class ResumeService {
  constructor(
    private readonly http: HttpClient,
    private readonly api: ApiService
  ) {}

  list(): Observable<Resume[]> {
    return this.http.get<Resume[]>(`${this.api.baseUrl}/resumes`);
  }

  upload(file: File): Observable<Resume> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<Resume>(`${this.api.baseUrl}/resumes/upload`, formData);
  }

  process(resumeId: number): Observable<ProfessionalProfile> {
    return this.http.post<ProfessionalProfile>(
      `${this.api.baseUrl}/resumes/${resumeId}/process`,
      {}
    );
  }

  getActiveProfile(): Observable<ProfessionalProfile> {
    return this.http.get<ProfessionalProfile>(`${this.api.baseUrl}/resumes/active/profile`);
  }
}
