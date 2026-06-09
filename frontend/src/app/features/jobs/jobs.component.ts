import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  LucideBookmark,
  LucideBriefcaseBusiness,
  LucideCheckCircle,
  LucideCircleHelp,
  LucideClock,
  LucideEuro,
  LucideExternalLink,
  LucideMapPin,
  LucideMonitor,
  LucidePlus,
  LucideRefreshCw,
  LucideSend,
  LucideSparkles,
  LucideStar,
  LucideUserRound,
  LucideX
} from '@lucide/angular';

import { FeedbackService, InteractionType } from '../feedback/feedback.service';
import { ProfessionalProfile, ResumeService } from '../resumes/resume.service';
import { Job, JobRecommendation, JobSearchTask, JobService } from './job.service';

type SalaryFilter = 'all' | 'known' | '30000' | '40000' | '50000';
type RoleFilter = 'all' | 'backend' | 'fullstack' | 'frontend' | 'data' | 'devops' | 'other';

@Component({
  selector: 'app-jobs',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    LucideBookmark,
    LucideBriefcaseBusiness,
    LucideCheckCircle,
    LucideCircleHelp,
    LucideClock,
    LucideEuro,
    LucideExternalLink,
    LucideMapPin,
    LucideMonitor,
    LucidePlus,
    LucideRefreshCw,
    LucideSend,
    LucideSparkles,
    LucideStar,
    LucideUserRound,
    LucideX
  ],
  templateUrl: './jobs.component.html',
  styleUrl: './jobs.component.scss'
})
export class JobsComponent implements OnInit, OnDestroy {
  recommendations: JobRecommendation[] = [];
  totalRecommendations = 0;
  profile: ProfessionalProfile | null = null;
  statusMessage = '';
  errorMessage = '';
  isLoading = false;
  isLoadingMore = false;
  loadingMessage = 'Cargando ofertas...';
  slowSearch = false;
  modalityFilter = 'all';
  salaryFilter: SalaryFilter = 'all';
  locationFilter = 'all';
  roleFilter: RoleFilter = 'all';
  readonly skeletonRows = Array.from({ length: 3 });
  readonly pageSize = 20;

  private readonly interactionByJob: Record<number, InteractionType> = {};
  private pollTimer: ReturnType<typeof setTimeout> | null = null;
  private slowTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly feedbackService: FeedbackService,
    private readonly jobService: JobService,
    private readonly resumeService: ResumeService
  ) {}

  ngOnInit(): void {
    this.loadProfile();
    const cachedRecommendations = this.jobService.getCachedRecommendations();
    if (cachedRecommendations) {
      this.recommendations = cachedRecommendations.items;
      this.totalRecommendations = cachedRecommendations.total;
      return;
    }
    this.loadRecommendations('Cargando ofertas...');
  }

  ngOnDestroy(): void {
    this.clearTimers();
  }

  get filteredRecommendations(): JobRecommendation[] {
    return this.recommendations.filter((item) => {
      const job = item.job;
      const modalityMatches =
        this.modalityFilter === 'all' ||
        this.normalize(job.modality).includes(this.modalityFilter);
      const locationMatches =
        this.locationFilter === 'all' || job.location === this.locationFilter;
      const roleMatches =
        this.roleFilter === 'all' || this.classifyRole(job.title) === this.roleFilter;
      return modalityMatches && locationMatches && roleMatches && this.matchesSalary(job);
    });
  }

  get hasMoreRecommendations(): boolean {
    return this.recommendations.length < this.totalRecommendations;
  }

  get locationOptions(): string[] {
    return Array.from(
      new Set(
        this.recommendations
          .map((item) => item.job.location?.trim())
          .filter((location): location is string => Boolean(location))
      )
    ).sort((left, right) => left.localeCompare(right, 'es'));
  }

  get profileContext(): string {
    const profileName =
      this.profile?.analysis?.primary_profile?.name ||
      this.profile?.profile_type ||
      'Perfil profesional';
    const skills = (this.profile?.technologies ?? []).slice(0, 3);
    return skills.length ? `${profileName} · ${skills.join(' · ')}` : profileName;
  }

  searchForProfile(): void {
    this.clearTimers();
    this.jobService.clearRecommendedCache();
    this.showLoading('Buscando ofertas en segundo plano...');
    this.statusMessage = '';
    this.errorMessage = '';

    this.jobService.startProfileSearch().subscribe({
      next: (task) => this.pollSearch(task.task_id),
      error: (error) => {
        this.hideLoading();
        this.errorMessage = this.extractError(error);
      }
    });
  }

  clearFilters(): void {
    this.modalityFilter = 'all';
    this.salaryFilter = 'all';
    this.locationFilter = 'all';
    this.roleFilter = 'all';
  }

  loadMore(): void {
    if (this.isLoadingMore || !this.hasMoreRecommendations) {
      return;
    }
    this.loadRecommendations(undefined, true);
  }

  summary(text: string | null): string {
    if (!text) {
      return 'La oferta no incluye un resumen.';
    }
    return text.length > 280 ? `${text.slice(0, 280).trim()}...` : text;
  }

  sourceLabel(source: string): string {
    const labels: Record<string, string> = {
      tecnoempleo: 'Tecnoempleo',
      infojobs: 'InfoJobs',
      manual: 'Carga manual',
      import: 'CSV/JSON'
    };
    return labels[source] ?? source;
  }

  sourceInitials(source: string): string {
    const initials: Record<string, string> = {
      tecnoempleo: 'TE',
      infojobs: 'IJ',
      manual: 'SM',
      import: 'SM'
    };
    return initials[source] ?? source.slice(0, 2).toUpperCase();
  }

  sourceClass(source: string): string {
    return `source-${this.normalize(source).replace(/\s+/g, '-')}`;
  }

  publicationLabel(job: Job): string {
    const dateValue = job.published_at || job.created_at;
    const date = new Date(dateValue);
    if (Number.isNaN(date.getTime())) {
      return 'Fecha no indicada';
    }

    const elapsedHours = Math.max(0, Math.floor((Date.now() - date.getTime()) / 3_600_000));
    const prefix = job.published_at ? 'Publicado' : 'Encontrado';
    if (elapsedHours < 1) {
      return `${prefix} hace menos de una hora`;
    }
    if (elapsedHours < 24) {
      return `${prefix} hace ${elapsedHours} ${elapsedHours === 1 ? 'hora' : 'horas'}`;
    }
    const days = Math.floor(elapsedHours / 24);
    if (days < 30) {
      return `${prefix} hace ${days} ${days === 1 ? 'día' : 'días'}`;
    }
    return `${prefix} el ${new Intl.DateTimeFormat('es-ES').format(date)}`;
  }

  salaryLabel(job: Job): string {
    const currency = job.salary_currency || 'EUR';
    if (job.salary_min && job.salary_max && job.salary_min !== job.salary_max) {
      return `${this.formatSalary(job.salary_min, currency)} - ${this.formatSalary(job.salary_max, currency)}`;
    }
    const salary = job.salary_min || job.salary_max;
    return salary ? this.formatSalary(salary, currency) : 'Salario no indicado';
  }

  modalityLabel(modality: string | null): string {
    const normalized = this.normalize(modality);
    if (normalized.includes('remoto')) {
      return 'Remoto';
    }
    if (normalized.includes('hibrido')) {
      return 'Híbrido';
    }
    if (normalized.includes('presencial')) {
      return 'Presencial';
    }
    return 'Modalidad no indicada';
  }

  modalityClass(modality: string | null): string {
    const normalized = this.normalize(modality);
    if (normalized.includes('remoto')) {
      return 'remote';
    }
    if (normalized.includes('hibrido')) {
      return 'hybrid';
    }
    return 'onsite';
  }

  contractLabel(job: Job): string {
    return job.contract_type || 'Contrato no indicado';
  }

  requirementSkills(item: JobRecommendation): string[] {
    const requirements = (item.job.requirements ?? '')
      .split(/[,;|]/)
      .map((skill) => skill.trim())
      .filter(
        (skill) =>
          skill.length > 0 &&
          skill.length <= 36 &&
          !this.normalize(skill).includes('requisitos no estructurados')
      );
    return Array.from(
      new Set([...requirements, ...item.matching_skills, ...item.missing_skills])
    ).slice(0, 9);
  }

  recommendationReason(item: JobRecommendation): string {
    const matching = item.matching_skills.slice(0, 3);
    if (matching.length) {
      return `Tu experiencia en ${this.joinNaturally(matching)} coincide con requisitos relevantes del puesto.`;
    }
    if (item.semantic_score >= 60) {
      return 'El contenido global de tu CV presenta una afinidad semántica relevante con esta oferta.';
    }
    return 'La oferta se aproxima a tu perfil profesional y puede ampliar tus oportunidades.';
  }

  compatibilityLabel(score: number): string {
    if (score >= 85) {
      return 'Muy alta compatibilidad';
    }
    if (score >= 70) {
      return 'Alta compatibilidad';
    }
    if (score >= 55) {
      return 'Buena compatibilidad';
    }
    return 'Compatibilidad moderada';
  }

  compatibilityClass(score: number): string {
    if (score >= 85) {
      return 'very-high';
    }
    if (score >= 70) {
      return 'high';
    }
    if (score >= 55) {
      return 'good';
    }
    return 'moderate';
  }

  openOffer(item: JobRecommendation): void {
    if (!item.job.url) {
      return;
    }
    window.open(item.job.url, '_blank', 'noopener,noreferrer');
    this.sendFeedback(item, 'viewed', false);
  }

  sendFeedback(
    item: JobRecommendation,
    interactionType: InteractionType,
    showConfirmation = true
  ): void {
    this.feedbackService.create(item.job.id, interactionType).subscribe({
      next: () => {
        this.interactionByJob[item.job.id] = interactionType;
        if (showConfirmation) {
          const labels: Record<InteractionType, string> = {
            viewed: 'vista',
            saved: 'guardada',
            discarded: 'descartada',
            applied: 'marcada como postulada'
          };
          this.statusMessage = `Oferta ${labels[interactionType]} correctamente.`;
        }
        this.errorMessage = '';
      },
      error: () => {
        this.statusMessage = '';
        this.errorMessage = 'No se pudo registrar la acción sobre la oferta.';
      }
    });
  }

  isInteraction(jobId: number, interactionType: InteractionType): boolean {
    return this.interactionByJob[jobId] === interactionType;
  }

  private loadProfile(): void {
    this.resumeService.getActiveProfile().subscribe({
      next: (profile) => {
        this.profile = profile;
      },
      error: () => {
        this.profile = null;
      }
    });
  }

  private loadRecommendations(loadingMessage?: string, append = false): void {
    if (loadingMessage) {
      this.showLoading(loadingMessage);
    }
    if (append) {
      this.isLoadingMore = true;
    }
    const offset = append ? this.recommendations.length : 0;
    this.jobService.recommended(this.pageSize, offset).subscribe({
      next: (page) => {
        if (append) {
          const existingIds = new Set(this.recommendations.map((item) => item.job.id));
          this.recommendations = [
            ...this.recommendations,
            ...page.items.filter((item) => !existingIds.has(item.job.id))
          ];
        } else {
          this.recommendations = page.items;
        }
        this.totalRecommendations = page.total;
        this.jobService.setRecommendedCache(
          this.recommendations,
          this.totalRecommendations
        );
        this.isLoadingMore = false;
        if (loadingMessage) {
          this.hideLoading();
        }
      },
      error: (error) => {
        if (!append) {
          this.recommendations = [];
          this.totalRecommendations = 0;
        }
        this.isLoadingMore = false;
        if (loadingMessage) {
          this.hideLoading();
        }
        this.errorMessage = this.extractError(error);
      }
    });
  }

  private showLoading(message: string): void {
    this.loadingMessage = message;
    this.isLoading = true;
    this.slowSearch = false;
    this.startSlowTimer();
  }

  private hideLoading(): void {
    this.isLoading = false;
    this.slowSearch = false;
    this.clearSlowTimer();
  }

  private pollSearch(taskId: string): void {
    this.jobService.searchStatus(taskId).subscribe({
      next: (task) => {
        this.loadingMessage = task.message || 'Buscando ofertas en segundo plano...';
        if (task.status === 'completed') {
          this.statusMessage = this.searchSummary(task);
          this.loadRecommendations('Ordenando ofertas recomendadas...');
          return;
        }
        if (task.status === 'failed') {
          this.hideLoading();
          this.errorMessage = task.error || 'La búsqueda ha fallado.';
          return;
        }
        this.pollTimer = setTimeout(() => this.pollSearch(taskId), 2000);
      },
      error: () => {
        this.hideLoading();
        this.errorMessage = 'No se pudo consultar el estado de la búsqueda.';
      }
    });
  }

  private searchSummary(task: JobSearchTask): string {
    const sources = task.sources?.items ?? [];
    const sourceSummary = sources
      .map(
        (source) =>
          `${this.sourceLabel(source.source)}: ${source.imported} nuevas y ${source.updated ?? 0} actualizadas`
      )
      .join(' · ');
    return sourceSummary
      ? `Búsqueda terminada. ${sourceSummary}.`
      : `Búsqueda terminada. ${task.imported} nuevas y ${task.updated} actualizadas.`;
  }

  private matchesSalary(job: Job): boolean {
    if (this.salaryFilter === 'all') {
      return true;
    }
    const maximum = job.salary_max || job.salary_min;
    if (this.salaryFilter === 'known') {
      return maximum !== null;
    }
    return maximum !== null && maximum >= Number(this.salaryFilter);
  }

  private classifyRole(title: string): RoleFilter {
    const normalized = this.normalize(title);
    if (/full.?stack/.test(normalized)) {
      return 'fullstack';
    }
    if (/(frontend|front end|angular|react|vue)/.test(normalized)) {
      return 'frontend';
    }
    if (/(data|datos|machine learning|inteligencia artificial| ia |ai engineer)/.test(` ${normalized} `)) {
      return 'data';
    }
    if (/(devops|cloud|sre|platform|sistemas)/.test(normalized)) {
      return 'devops';
    }
    if (/(backend|back end|java|python|api)/.test(normalized)) {
      return 'backend';
    }
    return 'other';
  }

  private formatSalary(value: number, currency: string): string {
    return new Intl.NumberFormat('es-ES', {
      style: 'currency',
      currency,
      maximumFractionDigits: 0
    }).format(value);
  }

  private joinNaturally(items: string[]): string {
    if (items.length <= 1) {
      return items[0] ?? '';
    }
    return `${items.slice(0, -1).join(', ')} y ${items[items.length - 1]}`;
  }

  private normalize(value: string | null): string {
    return (value ?? '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();
  }

  private startSlowTimer(): void {
    this.clearSlowTimer();
    this.slowTimer = setTimeout(() => {
      if (this.isLoading) {
        this.slowSearch = true;
      }
    }, 15000);
  }

  private clearTimers(): void {
    if (this.pollTimer) {
      clearTimeout(this.pollTimer);
      this.pollTimer = null;
    }
    this.clearSlowTimer();
  }

  private clearSlowTimer(): void {
    if (this.slowTimer) {
      clearTimeout(this.slowTimer);
      this.slowTimer = null;
    }
  }

  private extractError(error: unknown): string {
    if (typeof error === 'object' && error && 'error' in error) {
      const backendError = (error as { error?: { detail?: string } }).error;
      return backendError?.detail ?? 'Procesa primero tu CV y vuelve a intentarlo.';
    }
    return 'Procesa primero tu CV y vuelve a intentarlo.';
  }
}
