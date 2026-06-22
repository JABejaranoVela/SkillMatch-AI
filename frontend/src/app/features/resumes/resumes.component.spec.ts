import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { JobService } from '../jobs/job.service';
import { ProfessionalProfile, Resume, ResumeService } from './resume.service';
import { ResumesComponent } from './resumes.component';

describe('ResumesComponent', () => {
  let fixture: ComponentFixture<ResumesComponent>;
  let component: ResumesComponent;
  let resumeService: jasmine.SpyObj<ResumeService>;
  let jobService: jasmine.SpyObj<JobService>;

  const resume: Resume = {
    id: 10,
    filename: 'cv.pdf',
    file_type: '.pdf',
    status: 'processed',
    is_active: true,
    created_at: '2026-06-11T10:00:00Z',
    processed_at: '2026-06-11T10:01:00Z'
  };

  const profile: ProfessionalProfile = {
    id: 20,
    profile_type: 'Full Stack Developer',
    summary: 'Perfil detectado',
    experience_years: 2,
    education: null,
    languages: ['Español'],
    technologies: ['Angular', 'Python'],
    analysis: null
  };

  async function createComponent(resumes: Resume[] = []): Promise<void> {
    resumeService = jasmine.createSpyObj<ResumeService>(
      'ResumeService',
      ['list', 'upload', 'process', 'getActiveProfile', 'delete']
    );
    jobService = jasmine.createSpyObj<JobService>('JobService', ['clearRecommendedCache']);

    resumeService.list.and.returnValue(of(resumes));
    resumeService.upload.and.returnValue(of({ ...resume, status: 'uploaded' }));
    resumeService.process.and.returnValue(of(profile));
    resumeService.getActiveProfile.and.returnValue(of(profile));
    resumeService.delete.and.returnValue(of(void 0));

    await TestBed.configureTestingModule({
      imports: [ResumesComponent],
      providers: [
        provideRouter([]),
        { provide: ResumeService, useValue: resumeService },
        { provide: JobService, useValue: jobService }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(ResumesComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  afterEach(() => TestBed.resetTestingModule());

  it('requires consent before uploading a CV', async () => {
    await createComponent();

    component.onFileSelected(fileEvent(new File(['pdf'], 'cv.pdf', { type: 'application/pdf' })));

    expect(resumeService.upload).not.toHaveBeenCalled();
    expect(component.errorMessage).toContain('Acepta el aviso');
  });

  it('uploads and processes when consent is accepted', async () => {
    await createComponent();
    component.consentAccepted = true;

    component.onFileSelected(fileEvent(new File(['pdf'], 'cv.pdf', { type: 'application/pdf' })));

    expect(resumeService.upload).toHaveBeenCalled();
    expect(resumeService.process).toHaveBeenCalledWith(resume.id);
    expect(jobService.clearRecommendedCache).toHaveBeenCalled();
  });

  it('asks for confirmation before deleting the active CV', async () => {
    await createComponent([resume]);
    spyOn(window, 'confirm').and.returnValue(false);

    component.deleteActiveResume();

    expect(window.confirm).toHaveBeenCalled();
    expect(resumeService.delete).not.toHaveBeenCalled();
  });

  it('deletes the active CV and clears local state after confirmation', async () => {
    await createComponent([resume]);
    spyOn(window, 'confirm').and.returnValue(true);
    resumeService.list.calls.reset();
    resumeService.list.and.returnValue(of([]));

    component.deleteActiveResume();

    expect(resumeService.delete).toHaveBeenCalledWith(resume.id);
    expect(jobService.clearRecommendedCache).toHaveBeenCalled();
    expect(component.resumes).toEqual([]);
    expect(component.profile).toBeNull();
    expect(component.statusMessage).toContain('eliminado');
    expect(resumeService.list).toHaveBeenCalled();
  });

  it('shows a safe error if deletion fails', async () => {
    await createComponent([resume]);
    spyOn(window, 'confirm').and.returnValue(true);
    resumeService.delete.and.returnValue(
      throwError(() => ({ error: { detail: 'No se ha podido eliminar el CV en este momento.' } }))
    );

    component.deleteActiveResume();

    expect(component.statusMessage).toBe('No se pudo eliminar el CV.');
    expect(component.errorMessage).toBe('No se ha podido eliminar el CV en este momento.');
  });

  function fileEvent(file: File): Event {
    return {
      target: {
        files: [file],
        value: ''
      }
    } as unknown as Event;
  }
});
