import { Component, OnInit } from '@angular/core';

import { JobRecommendation, JobService } from './job.service';

@Component({
  selector: 'app-jobs',
  standalone: true,
  templateUrl: './jobs.component.html',
  styleUrl: '../resumes/resumes.component.scss'
})
export class JobsComponent implements OnInit {
  recommendations: JobRecommendation[] = [];
  statusMessage = '';
  errorMessage = '';

  constructor(private readonly jobService: JobService) {}

  ngOnInit(): void {
    this.loadRecommendations();
  }

  searchForProfile(): void {
    this.statusMessage = 'Buscando ofertas reales en portales espanoles segun tu perfil...';
    this.errorMessage = '';

    this.jobService.syncForProfile().subscribe({
      next: (result) => {
        const sourceSummary = result.sources
          .map((source) => `${this.sourceLabel(source.source)}: ${source.imported} nuevas, ${source.updated ?? 0} actualizadas`)
          .join(' - ');
        this.statusMessage = `Busqueda para ${result.profile_type || 'tu perfil'} (${result.search_terms.join(', ')}). ${sourceSummary}.`;
        this.loadRecommendations();
      },
      error: (error) => {
        this.statusMessage = 'No se pudieron buscar ofertas espanolas para tu perfil.';
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
      remotive: 'Remotive',
      arbeitnow: 'Arbeitnow',
      tecnoempleo: 'Tecnoempleo',
      manual: 'Manual',
      import: 'CSV/JSON'
    };
    return labels[source] ?? source;
  }

  scoreLabel(item: JobRecommendation): string {
    return `Skills ${item.rules_score}% + IA semantica ${item.semantic_score}%`;
  }

  private loadRecommendations(): void {
    this.jobService.recommended().subscribe({
      next: (recommendations) => {
        this.recommendations = recommendations;
      },
      error: () => {
        this.recommendations = [];
      }
    });
  }

  private extractError(error: unknown): string {
    if (typeof error === 'object' && error && 'error' in error) {
      const backendError = (error as { error?: { detail?: string } }).error;
      return backendError?.detail ?? 'Procesa primero tu CV y vuelve a intentarlo.';
    }
    return 'Procesa primero tu CV y vuelve a intentarlo.';
  }
}
