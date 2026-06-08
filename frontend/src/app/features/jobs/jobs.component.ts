import { Component, OnDestroy, OnInit } from '@angular/core';

import { FeedbackService, InteractionType } from '../feedback/feedback.service';
import { JobRecommendation, JobSearchTask, JobService } from './job.service';

@Component({
  selector: 'app-jobs',
  standalone: true,
  templateUrl: './jobs.component.html',
  styleUrl: '../resumes/resumes.component.scss'
})
export class JobsComponent implements OnInit, OnDestroy {
  recommendations: JobRecommendation[] = [];
  statusMessage = '';
  errorMessage = '';
  isLoading = false;
  loadingMessage = 'Cargando ofertas...';
  slowSearch = false;
  readonly skeletonRows = Array.from({ length: 3 });

  private pollTimer: ReturnType<typeof setTimeout> | null = null;
  private slowTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly feedbackService: FeedbackService,
    private readonly jobService: JobService
  ) {}

  ngOnInit(): void {
    const cachedRecommendations = this.jobService.getCachedRecommendations();
    if (cachedRecommendations) {
      this.recommendations = cachedRecommendations;
      return;
    }
    this.loadRecommendations('Cargando ofertas...');
  }

  ngOnDestroy(): void {
    this.clearTimers();
  }

  searchForProfile(): void {
    this.clearTimers();
    this.jobService.clearRecommendedCache();
    this.showLoading('Buscando ofertas en segundo plano...');
    this.statusMessage = 'Buscando ofertas reales en portales españoles según tu perfil...';
    this.errorMessage = '';

    this.jobService.startProfileSearch().subscribe({
      next: (task) => {
        this.pollSearch(task.task_id);
      },
      error: (error) => {
        this.hideLoading();
        this.statusMessage = 'No se pudieron buscar ofertas españolas para tu perfil.';
        this.errorMessage = this.extractError(error);
      }
    });
  }

  summary(text: string | null): string {
    if (!text) {
      return 'Sin resumen disponible.';
    }
    return text.length > 360 ? `${text.slice(0, 360)}...` : text;
  }

  sourceLabel(source: string): string {
    const labels: Record<string, string> = {
      tecnoempleo: 'Tecnoempleo',
      infojobs: 'InfoJobs',
      manual: 'Manual',
      import: 'CSV/JSON'
    };
    return labels[source] ?? source;
  }

  scoreLabel(item: JobRecommendation): string {
    return `Skills ${item.rules_score}% + IA semántica ${item.semantic_score}%`;
  }

  sendFeedback(item: JobRecommendation, interactionType: InteractionType): void {
    this.feedbackService.create(item.job.id, interactionType).subscribe({
      next: () => {
        const labels: Record<InteractionType, string> = {
          viewed: 'vista',
          saved: 'guardada',
          discarded: 'descartada',
          applied: 'marcada como postulada'
        };
        this.statusMessage = `Oferta ${labels[interactionType]} correctamente.`;
        this.errorMessage = '';
      },
      error: () => {
        this.statusMessage = '';
        this.errorMessage = 'No se pudo registrar la acción sobre la oferta.';
      }
    });
  }

  private loadRecommendations(loadingMessage?: string): void {
    if (loadingMessage) {
      this.showLoading(loadingMessage);
    }
    this.jobService.recommended().subscribe({
      next: (recommendations) => {
        this.recommendations = recommendations;
        this.jobService.setRecommendedCache(recommendations);
        this.hideLoading();
      },
      error: () => {
        this.recommendations = [];
        this.hideLoading();
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
          this.statusMessage = 'No se pudieron buscar ofertas para tu perfil.';
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
      .map((source) => `${this.sourceLabel(source.source)}: ${source.imported} nuevas, ${source.updated ?? 0} actualizadas`)
      .join(' - ');
    return sourceSummary
      ? `Búsqueda terminada. ${sourceSummary}.`
      : `Búsqueda terminada. ${task.imported} nuevas, ${task.updated} actualizadas.`;
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
