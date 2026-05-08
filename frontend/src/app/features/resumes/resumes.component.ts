import { Component, OnInit } from '@angular/core';

import { ProfessionalProfile, Resume, ResumeService } from './resume.service';

@Component({
  selector: 'app-resumes',
  standalone: true,
  templateUrl: './resumes.component.html',
  styleUrl: './resumes.component.scss'
})
export class ResumesComponent implements OnInit {
  resumes: Resume[] = [];
  profile: ProfessionalProfile | null = null;
  selectedFile: File | null = null;
  statusMessage = '';
  errorMessage = '';

  constructor(private readonly resumeService: ResumeService) {}

  ngOnInit(): void {
    this.loadResumes();
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedFile = input.files?.[0] ?? null;
  }

  upload(): void {
    if (!this.selectedFile) {
      this.statusMessage = 'Selecciona un archivo PDF o DOCX.';
      this.errorMessage = '';
      return;
    }

    this.resumeService.upload(this.selectedFile).subscribe({
      next: () => {
        this.statusMessage = 'CV subido correctamente.';
        this.errorMessage = '';
        this.profile = null;
        this.selectedFile = null;
        this.loadResumes();
      },
      error: (error) => {
        this.statusMessage = 'No se pudo subir el CV.';
        this.errorMessage = this.extractError(error);
      }
    });
  }

  process(resumeId: number): void {
    this.statusMessage = 'Procesando CV...';
    this.errorMessage = '';
    this.resumeService.process(resumeId).subscribe({
      next: (profile) => {
        this.profile = profile;
        this.statusMessage = 'CV procesado correctamente.';
        this.errorMessage = '';
        this.loadResumes();
      },
      error: (error) => {
        this.statusMessage = 'No se pudo procesar el CV.';
        this.errorMessage = this.extractError(error);
      }
    });
  }

  private loadResumes(): void {
    this.resumeService.list().subscribe({
      next: (resumes) => {
        this.resumes = resumes;
        if (resumes.some((resume) => resume.status === 'processed')) {
          this.loadActiveProfile();
        } else {
          this.profile = null;
        }
      }
    });
  }

  private loadActiveProfile(): void {
    this.resumeService.getActiveProfile().subscribe({
      next: (profile) => {
        this.profile = profile;
      },
      error: () => {
        this.profile = null;
      }
    });
  }

  private extractError(error: unknown): string {
    if (typeof error === 'object' && error && 'error' in error) {
      const backendError = (error as { error?: { detail?: string } }).error;
      return backendError?.detail ?? 'Revisa que el archivo sea valido y vuelve a intentarlo.';
    }
    return 'Revisa que el archivo sea valido y vuelve a intentarlo.';
  }
}
