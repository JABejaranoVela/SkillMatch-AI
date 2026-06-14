import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { BehaviorSubject, of, throwError } from 'rxjs';

import { AuthService, AuthUser } from '../auth/auth.service';
import { FeedbackJob, FeedbackService } from '../feedback/feedback.service';
import { JobRecommendationPage, JobService } from '../jobs/job.service';
import { ProfessionalProfile, Resume, ResumeService } from '../resumes/resume.service';
import { DashboardComponent } from './dashboard.component';

describe('DashboardComponent', () => {
  let fixture: ComponentFixture<DashboardComponent>;
  let component: DashboardComponent;
  let userSubject: BehaviorSubject<AuthUser | null>;
  let resumeService: jasmine.SpyObj<ResumeService>;
  let jobService: jasmine.SpyObj<JobService>;
  let feedbackService: jasmine.SpyObj<FeedbackService>;

  const activeUser: AuthUser = {
    id: 1,
    email: 'demo@skillmatch.com',
    full_name: 'Demo SkillMatch',
    role: 'user',
    status: 'active',
    email_verified_at: '2026-06-11T10:00:00Z'
  };

  const processedResume: Resume = {
    id: 10,
    filename: 'demo-cv.pdf',
    file_type: 'application/pdf',
    status: 'processed',
    is_active: true,
    created_at: '2026-06-10T10:00:00Z',
    processed_at: '2026-06-10T10:05:00Z'
  };

  const profile: ProfessionalProfile = {
    id: 20,
    profile_type: 'Full Stack Developer',
    summary: null,
    experience_years: 4,
    education: null,
    languages: ['Español'],
    technologies: ['Angular', 'Python'],
    analysis: null
  };

  const recommendationPage: JobRecommendationPage = {
    items: Array.from({ length: 5 }, (_, index) => ({
      job: {
        id: index + 1,
        title: `Oferta ${index + 1}`,
        company: `Empresa ${index + 1}`,
        description: 'Descripción',
        requirements: null,
        location: 'Madrid',
        modality: 'Híbrido',
        salary_min: null,
        salary_max: null,
        salary_currency: null,
        contract_type: null,
        published_at: null,
        source: 'test',
        external_id: null,
        url: `https://example.com/jobs/${index + 1}`,
        status: 'active',
        created_at: '2026-06-11T10:00:00Z'
      },
      final_score: 90 - index,
      rules_score: 90,
      semantic_score: 90,
      matching_skills: ['Angular'],
      missing_skills: []
    })),
    total: 47,
    limit: 3,
    offset: 0,
    has_more: true
  };

  const selectedOffers: FeedbackJob[] = [
    {
      id: 1,
      job_id: 1,
      match_result_id: 1,
      interaction_type: 'saved',
      created_at: '2026-06-11T10:00:00Z',
      job: recommendationPage.items[0].job,
      final_score: 90,
      matching_skills: ['Angular'],
      missing_skills: []
    },
    {
      id: 2,
      job_id: 2,
      match_result_id: 2,
      interaction_type: 'applied',
      created_at: '2026-06-11T10:00:00Z',
      job: recommendationPage.items[1].job,
      final_score: 89,
      matching_skills: ['Python'],
      missing_skills: []
    }
  ];

  async function createComponent(options: {
    user?: AuthUser;
    resumes?: Resume[];
    recommendations?: JobRecommendationPage;
    offers?: FeedbackJob[];
    failResume?: boolean;
    failRecommendations?: boolean;
    failOffers?: boolean;
    failProfile?: boolean;
  } = {}): Promise<void> {
    userSubject = new BehaviorSubject<AuthUser | null>(options.user ?? activeUser);
    resumeService = jasmine.createSpyObj<ResumeService>(
      'ResumeService',
      ['list', 'getActiveProfile']
    );
    jobService = jasmine.createSpyObj<JobService>('JobService', ['recommended']);
    feedbackService = jasmine.createSpyObj<FeedbackService>('FeedbackService', ['listJobs']);

    resumeService.list.and.returnValue(
      options.failResume
        ? throwError(() => new Error('resume unavailable'))
        : of(options.resumes ?? [processedResume])
    );
    resumeService.getActiveProfile.and.returnValue(
      options.failProfile
        ? throwError(() => new Error('profile unavailable'))
        : of(profile)
    );
    jobService.recommended.and.returnValue(
      options.failRecommendations
        ? throwError(() => new Error('recommendations unavailable'))
        : of(options.recommendations ?? recommendationPage)
    );
    feedbackService.listJobs.and.returnValue(
      options.failOffers
        ? throwError(() => new Error('offers unavailable'))
        : of(options.offers ?? selectedOffers)
    );

    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: { user$: userSubject.asObservable() }
        },
        { provide: ResumeService, useValue: resumeService },
        { provide: JobService, useValue: jobService },
        { provide: FeedbackService, useValue: feedbackService }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(DashboardComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  afterEach(() => TestBed.resetTestingModule());

  it('uses the user name in the greeting', async () => {
    await createComponent();

    expect(fixture.nativeElement.querySelector('.welcome h1').textContent)
      .toContain('Hola, Demo SkillMatch');
  });

  it('uses the email prefix when the user has no name', async () => {
    await createComponent({ user: { ...activeUser, full_name: null } });

    expect(fixture.nativeElement.querySelector('.welcome h1').textContent)
      .toContain('Hola, demo');
  });

  it('shows the upload action when there is no active resume', async () => {
    await createComponent({ resumes: [] });

    expect(component.nextStep.actionLabel).toBe('Subir mi CV');
    expect(component.nextStep.route).toBe('/cv');
    expect(fixture.nativeElement.textContent).toContain('Empieza subiendo tu CV');
    expect(jobService.recommended).not.toHaveBeenCalled();
  });

  it('directs pending and failed resumes to the resume page', async () => {
    await createComponent({
      resumes: [{ ...processedResume, status: 'failed' }]
    });

    expect(component.nextStep.actionLabel).toBe('Ver mi CV');
    expect(component.nextStep.route).toBe('/cv');
    expect(fixture.nativeElement.textContent).toContain('Revisa tu CV');
  });

  it('shows the detected profile and job search action for a processed resume', async () => {
    await createComponent();

    expect(component.profileName).toBe('Full Stack Developer');
    expect(component.nextStep.route).toBe('/jobs');
    expect(component.nextStep.actionLabel).toBe('Buscar más ofertas');
    expect(fixture.nativeElement.textContent).toContain('Tu CV ya está analizado');
  });

  it('shows recommendation and selected-offer totals in summary cards', async () => {
    await createComponent();

    expect(component.totalRecommendations).toBe(47);
    expect(component.savedCount).toBe(1);
    expect(component.appliedCount).toBe(1);
    expect(fixture.nativeElement.textContent).toContain('47');
    expect(fixture.nativeElement.textContent).toContain('guardadas');
    expect(fixture.nativeElement.textContent).toContain('postulada');
  });

  it('renders at most three recommendations', async () => {
    await createComponent();

    expect(component.recommendations.length).toBe(3);
    expect(fixture.nativeElement.querySelectorAll('.offer-row').length).toBe(3);
  });

  it('shows the empty state when there are no recommendations', async () => {
    await createComponent({
      recommendations: { ...recommendationPage, items: [], total: 0, has_more: false }
    });

    expect(fixture.nativeElement.textContent)
      .toContain('Busca ofertas compatibles para ver recomendaciones aquí.');
  });

  it('reflects all completed checklist states', async () => {
    await createComponent();

    expect(component.hasDetectedSkills).toBeTrue();
    expect(fixture.nativeElement.querySelectorAll('.checklist li.completed').length).toBe(5);
  });

  it('keeps the rest of the dashboard available after partial request errors', async () => {
    await createComponent({
      failProfile: true,
      failRecommendations: true,
      failOffers: true
    });

    expect(component.activeResume).toEqual(processedResume);
    expect(component.profileUnavailable).toBeTrue();
    expect(component.recommendationsUnavailable).toBeTrue();
    expect(component.selectedOffersUnavailable).toBeTrue();
    expect(fixture.nativeElement.textContent).toContain('demo-cv.pdf');
    expect(fixture.nativeElement.textContent).toContain('Recomendaciones no disponibles');
  });
});
