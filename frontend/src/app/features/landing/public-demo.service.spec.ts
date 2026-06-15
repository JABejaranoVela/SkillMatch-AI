import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { PublicDemoAnalysis, PublicDemoService } from './public-demo.service';

describe('PublicDemoService', () => {
  let service: PublicDemoService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        PublicDemoService,
        provideHttpClient(),
        provideHttpClientTesting()
      ]
    });
    service = TestBed.inject(PublicDemoService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
    TestBed.resetTestingModule();
  });

  it('uploads the PDF to the public demo endpoint', () => {
    const file = new File(['pdf'], 'cv.pdf', { type: 'application/pdf' });
    const result: PublicDemoAnalysis = {
      profile_type: 'Backend Developer',
      summary: 'Perfil técnico',
      skills: ['Python'],
      languages: [],
      education: [],
      experience_summary: null,
      is_demo: true
    };

    service.analyzeCv(file).subscribe((response) => {
      expect(response).toEqual(result);
    });

    const request = httpTesting.expectOne('/api/v1/public/demo/analyze-cv');
    expect(request.request.method).toBe('POST');
    expect(request.request.body instanceof FormData).toBeTrue();
    expect((request.request.body as FormData).get('file')).toBe(file);
    request.flush(result);
  });
});
