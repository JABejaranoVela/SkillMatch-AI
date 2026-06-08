import { DatePipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';

import { FeedbackJob, FeedbackService, InteractionType } from '../feedback/feedback.service';

type OfferFilter = 'all' | 'saved' | 'applied';

@Component({
  selector: 'app-saved-jobs',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './saved-jobs.component.html',
  styleUrl: '../resumes/resumes.component.scss'
})
export class SavedJobsComponent implements OnInit {
  offers: FeedbackJob[] = [];
  activeFilter: OfferFilter = 'all';
  statusMessage = '';
  errorMessage = '';
  isLoading = false;
  loadingMessage = 'Cargando tus ofertas...';

  constructor(private readonly feedbackService: FeedbackService) {}

  ngOnInit(): void {
    this.loadOffers();
  }

  setFilter(filter: OfferFilter): void {
    this.activeFilter = filter;
    this.loadOffers();
  }

  changeStatus(offer: FeedbackJob, interactionType: InteractionType): void {
    this.feedbackService.create(offer.job.id, interactionType, offer.match_result_id ?? undefined).subscribe({
      next: () => {
        this.statusMessage = 'Estado de la oferta actualizado.';
        this.errorMessage = '';
        this.loadOffers();
      },
      error: () => {
        this.statusMessage = '';
        this.errorMessage = 'No se pudo actualizar el estado de la oferta.';
      }
    });
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

  interactionLabel(interactionType: InteractionType): string {
    const labels: Record<InteractionType, string> = {
      viewed: 'Vista',
      saved: 'Guardada',
      discarded: 'Descartada',
      applied: 'Postulado'
    };
    return labels[interactionType];
  }

  summary(text: string | null): string {
    if (!text) {
      return 'Sin resumen disponible.';
    }
    return text.length > 320 ? `${text.slice(0, 320)}...` : text;
  }

  private loadOffers(): void {
    this.isLoading = true;
    this.statusMessage = '';
    this.errorMessage = '';
    const interactionType = this.activeFilter === 'all' ? undefined : this.activeFilter;
    this.feedbackService.listJobs(interactionType).subscribe({
      next: (offers) => {
        this.offers = offers;
        this.isLoading = false;
      },
      error: () => {
        this.offers = [];
        this.isLoading = false;
        this.errorMessage = 'No se pudieron cargar tus ofertas.';
      }
    });
  }
}
