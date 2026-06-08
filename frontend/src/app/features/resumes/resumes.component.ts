import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';

import { JobService } from '../jobs/job.service';
import { ProfessionalProfile, ProfileScore, Resume, ResumeService } from './resume.service';

interface SkillCategoryGroup {
  category: string;
  label: string;
  skills: string[];
}

@Component({
  selector: 'app-resumes',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './resumes.component.html',
  styleUrl: './resumes.component.scss'
})
export class ResumesComponent implements OnInit {
  resumes: Resume[] = [];
  profile: ProfessionalProfile | null = null;
  selectedFile: File | null = null;
  uploadedFileSize: number | null = null;
  statusMessage = '';
  errorMessage = '';
  isDragging = false;
  isUploading = false;
  isProcessing = false;
  showAllSkills = false;
  readonly skeletonRows = Array.from({ length: 3 });

  constructor(
    private readonly jobService: JobService,
    private readonly resumeService: ResumeService
  ) {}

  get activeResume(): Resume | null {
    return this.resumes[0] ?? null;
  }

  get visibleSkills(): string[] {
    const skills = this.profile?.technologies ?? [];
    return this.showAllSkills ? skills : skills.slice(0, 10);
  }

  get hasHiddenSkills(): boolean {
    return (this.profile?.technologies?.length ?? 0) > this.visibleSkills.length;
  }

  get isBusy(): boolean {
    return this.isUploading || this.isProcessing;
  }

  get loadingMessage(): string {
    if (this.isUploading) {
      return 'Subiendo CV...';
    }
    if (this.isProcessing) {
      return 'Analizando CV y detectando aptitudes...';
    }
    return '';
  }

  ngOnInit(): void {
    this.loadResumes();
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    input.value = '';
    if (file) {
      this.uploadSelectedFile(file);
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragging = true;
  }

  onDragLeave(): void {
    this.isDragging = false;
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragging = false;
    const file = event.dataTransfer?.files?.[0] ?? null;
    if (file) {
      this.uploadSelectedFile(file);
    }
  }

  process(resumeId: number): void {
    this.jobService.clearRecommendedCache();
    this.isProcessing = true;
    this.statusMessage = 'Analizando tu CV...';
    this.errorMessage = '';
    this.resumeService.process(resumeId).subscribe({
      next: (profile) => {
        this.profile = profile;
        this.showAllSkills = false;
        this.statusMessage = 'CV analizado correctamente.';
        this.errorMessage = '';
        this.isProcessing = false;
        this.loadResumes();
      },
      error: (error) => {
        this.statusMessage = 'No se pudo analizar el CV.';
        this.errorMessage = this.extractError(error);
        this.isProcessing = false;
      }
    });
  }

  toggleSkills(): void {
    this.showAllSkills = !this.showAllSkills;
  }

  fileSizeLabel(size: number | null): string {
    if (!size) {
      return 'Tamaño no disponible';
    }
    const mb = size / 1024 / 1024;
    return `${mb.toFixed(1)} MB`;
  }

  statusLabel(status: string): string {
    const labels: Record<string, string> = {
      uploaded: 'Pendiente',
      processing: 'Analizando',
      processed: 'Analizado',
      failed: 'Error'
    };
    return labels[status] ?? status;
  }

  statusClass(status: string): string {
    return `state-${status}`;
  }

  profileBadge(): string {
    const score = this.primaryProfileScore()?.score ?? 0;
    if (score >= 75) {
      return 'Alta afinidad';
    }
    if (score >= 45) {
      return 'Perfil suficiente';
    }
    return 'Perfil parcial';
  }

  primaryProfileScore(): ProfileScore | null {
    return this.profile?.analysis?.primary_profile ?? null;
  }

  secondaryProfileScore(): ProfileScore | null {
    return this.profile?.analysis?.secondary_profile ?? null;
  }

  topProfileScores(): ProfileScore[] {
    return (this.profile?.analysis?.profile_scores ?? [])
      .filter((score) => score.score > 0)
      .slice(0, 3);
  }

  profileRankLabel(index: number): string {
    return index === 0 ? 'Principal' : `Perfil ${index + 1}`;
  }

  profileScoreLabel(score: number | undefined): string {
    if (score === undefined || score === null) {
      return '0%';
    }
    return `${Math.round(score)}%`;
  }

  skillCategoryGroups(): SkillCategoryGroup[] {
    const categories = this.profile?.analysis?.skill_categories ?? {};
    return Object.entries(categories)
      .map(([category, skills]) => ({
        category,
        label: this.categoryLabel(category),
        skills
      }))
      .filter((group) => group.skills.length > 0)
      .sort((a, b) => b.skills.length - a.skills.length);
  }

  educationItems(): string[] {
    const raw = this.profile?.education?.['raw'];
    if (Array.isArray(raw) && raw.length) {
      return raw.map((item) => String(item));
    }
    if (typeof raw === 'string' && raw) {
      return [raw];
    }
    return [];
  }

  languages(): string[] {
    return this.profile?.languages?.length ? this.profile.languages : [];
  }

  languageLevel(language: string): string {
    const normalized = language.toLowerCase();
    if (normalized.includes('espanol') || normalized.includes('español')) {
      return 'Nativo';
    }
    if (normalized.includes('ingles') || normalized.includes('inglés')) {
      return 'Intermedio B2';
    }
    return 'Detectado';
  }

  experienceLabel(): string {
    const years = this.profile?.experience_years;
    if (years === null || years === undefined) {
      return 'No cuantificada';
    }
    if (years < 1) {
      const months = Math.max(1, Math.round(years * 12));
      return months === 1 ? '1 mes' : `${months} meses`;
    }
    if (years === 1) {
      return '1 año';
    }
    return `${years.toFixed(1).replace('.0', '')} años`;
  }

  private categoryLabel(category: string): string {
    const labels: Record<string, string> = {
      ai: 'IA y datos',
      api_documentation: 'Documentación API',
      architecture: 'Arquitectura',
      backend: 'Backend',
      cloud: 'Cloud',
      computer_science: 'Base técnica',
      data_engineering: 'Data engineering',
      data_format: 'Formatos',
      data_visualization: 'Visualizacion',
      database: 'Bases de datos',
      deployment: 'Despliegue',
      detected_technical_term: 'Detectadas por patrón',
      devops: 'DevOps',
      frontend: 'Frontend',
      operating_system: 'Sistemas',
      programming_language: 'Lenguajes',
      security: 'Seguridad',
      testing: 'Testing',
      tools: 'Herramientas'
    };
    return labels[category] ?? category;
  }

  private uploadSelectedFile(file: File): void {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      this.statusMessage = 'Selecciona un archivo PDF.';
      this.errorMessage = 'En esta pantalla solo se admite formato PDF.';
      return;
    }

    this.selectedFile = file;
    this.uploadedFileSize = file.size;
    this.isUploading = true;
    this.jobService.clearRecommendedCache();
    this.statusMessage = 'Subiendo CV...';
    this.errorMessage = '';

    this.resumeService.upload(file).subscribe({
      next: (resume) => {
        this.isUploading = false;
        this.profile = null;
        this.resumes = [resume];
        this.process(resume.id);
      },
      error: (error) => {
        this.statusMessage = 'No se pudo subir el CV.';
        this.errorMessage = this.extractError(error);
        this.isUploading = false;
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
        this.showAllSkills = false;
      },
      error: () => {
        this.profile = null;
      }
    });
  }

  private extractError(error: unknown): string {
    if (typeof error === 'object' && error && 'error' in error) {
      const backendError = (error as { error?: { detail?: string } }).error;
      return backendError?.detail ?? 'Revisa que el archivo sea válido y vuelve a intentarlo.';
    }
    return 'Revisa que el archivo sea válido y vuelve a intentarlo.';
  }
}
