import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '../../core/api.service';

export interface PublicDemoAnalysis {
  profile_type: string;
  summary: string;
  skills: string[];
  languages: string[];
  education: string[];
  experience_summary: string | null;
  is_demo: true;
}

@Injectable({ providedIn: 'root' })
export class PublicDemoService {
  constructor(
    private readonly http: HttpClient,
    private readonly api: ApiService
  ) {}

  analyzeCv(file: File): Observable<PublicDemoAnalysis> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<PublicDemoAnalysis>(
      `${this.api.baseUrl}/public/demo/analyze-cv`,
      formData
    );
  }
}
