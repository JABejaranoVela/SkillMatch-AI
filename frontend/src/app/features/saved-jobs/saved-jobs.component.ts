import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  LucideBookmark,
  LucideBriefcaseBusiness,
  LucideCheck,
  LucideCheckCircle,
  LucideClock,
  LucideEuro,
  LucideExternalLink,
  LucideFilter,
  LucideMapPin,
  LucideMonitor,
  LucideRefreshCw,
  LucideSend,
  LucideSlidersHorizontal,
  LucideStar,
  LucideX
} from '@lucide/angular';

import { FeedbackJob, FeedbackService, InteractionType } from '../feedback/feedback.service';
import { Job } from '../jobs/job.service';

type OfferFilter = 'all' | 'saved' | 'applied';
type SortOption = 'recent' | 'oldest' | 'compatibility' | 'title';

@Component({
  selector: 'app-saved-jobs',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    LucideBookmark,
    LucideBriefcaseBusiness,
    LucideCheck,
    LucideCheckCircle,
    LucideClock,
    LucideEuro,
    LucideExternalLink,
    LucideFilter,
    LucideMapPin,
    LucideMonitor,
    LucideRefreshCw,
    LucideSend,
    LucideSlidersHorizontal,
    LucideStar,
    LucideX
  ],
  templateUrl: './saved-jobs.component.html',
  styleUrl: './saved-jobs.component.scss'
})
export class SavedJobsComponent implements OnInit {
  offers: FeedbackJob[] = [];
  activeFilter: OfferFilter = 'all';
  sortOption: SortOption = 'recent';
  modalityFilter = 'all';
  sourceFilter = 'all';
  statusMessage = '';
  errorMessage = '';
  isLoading = false;
  showFilters = false;
  readonly skeletonRows = Array.from({ length: 3 });

  constructor(private readonly feedbackService: FeedbackService) {}

  ngOnInit(): void {
    this.loadOffers();
  }

  get filteredOffers(): FeedbackJob[] {
    const filtered = this.offers.filter((offer) => {
      const statusMatches =
        this.activeFilter === 'all' || offer.interaction_type === this.activeFilter;
      const modalityMatches =
        this.modalityFilter === 'all' ||
        this.normalize(offer.job.modality).includes(this.modalityFilter);
      const sourceMatches =
        this.sourceFilter === 'all' || offer.job.source === this.sourceFilter;
      return statusMatches && modalityMatches && sourceMatches;
    });

    return filtered.sort((left, right) => {
      if (this.sortOption === 'oldest') {
        return new Date(left.created_at).getTime() - new Date(right.created_at).getTime();
      }
      if (this.sortOption === 'compatibility') {
        return right.final_score - left.final_score;
      }
      if (this.sortOption === 'title') {
        return left.job.title.localeCompare(right.job.title, 'es');
      }
      return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
    });
  }

  get savedCount(): number {
    return this.offers.filter((offer) => offer.interaction_type === 'saved').length;
  }

  get appliedCount(): number {
    return this.offers.filter((offer) => offer.interaction_type === 'applied').length;
  }

  get sourceOptions(): { value: string; label: string }[] {
    const sources = Array.from(new Set(this.offers.map((offer) => offer.job.source)));
    return sources.map((source) => ({ value: source, label: this.sourceLabel(source) }));
  }

  setFilter(filter: OfferFilter): void {
    this.activeFilter = filter;
  }

  toggleFilters(): void {
    this.showFilters = !this.showFilters;
  }

  clearFilters(): void {
    this.modalityFilter = 'all';
    this.sourceFilter = 'all';
  }

  changeStatus(offer: FeedbackJob, interactionType: InteractionType): void {
    this.feedbackService
      .create(offer.job.id, interactionType, offer.match_result_id ?? undefined)
      .subscribe({
        next: () => {
          this.statusMessage =
            interactionType === 'discarded'
              ? 'La oferta se ha descartado.'
              : 'Estado de la oferta actualizado.';
          this.errorMessage = '';
          this.loadOffers(false);
        },
        error: () => {
          this.statusMessage = '';
          this.errorMessage = 'No se pudo actualizar el estado de la oferta.';
        }
      });
  }

  openOffer(offer: FeedbackJob): void {
    if (offer.job.url) {
      window.open(offer.job.url, '_blank', 'noopener,noreferrer');
    }
  }

  sourceLabel(source: string): string {
    const labels: Record<string, string> = {
      tecnoempleo: 'Tecnoempleo',
      infojobs: 'InfoJobs',
      manual: 'SkillMatch',
      import: 'SkillMatch'
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

  interactionLabel(interactionType: InteractionType): string {
    const labels: Record<InteractionType, string> = {
      viewed: 'Vista',
      saved: 'Guardada',
      discarded: 'Descartada',
      applied: 'Postulada'
    };
    return labels[interactionType];
  }

  interactionDateLabel(offer: FeedbackJob): string {
    const label = offer.interaction_type === 'applied' ? 'Postulada' : 'Guardada';
    const date = new Intl.DateTimeFormat('es-ES', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    }).format(new Date(offer.created_at));
    return `${label} el ${date}`;
  }

  summary(text: string | null): string {
    if (!text) {
      return 'La oferta no incluye un resumen.';
    }
    return text.length > 260 ? `${text.slice(0, 260).trim()}...` : text;
  }

  salaryLabel(job: Job): string {
    const salary = job.salary_max || job.salary_min;
    if (!salary) {
      return 'Salario no indicado';
    }
    const currency = job.salary_currency || 'EUR';
    if (job.salary_min && job.salary_max && job.salary_min !== job.salary_max) {
      return `${this.formatSalary(job.salary_min, currency)} - ${this.formatSalary(job.salary_max, currency)}`;
    }
    return this.formatSalary(salary, currency);
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

  requirementSkills(offer: FeedbackJob): string[] {
    const requirements = (offer.job.requirements ?? '')
      .split(/[,;|]/)
      .map((skill) => skill.trim())
      .filter(
        (skill) =>
          skill.length > 0 &&
          skill.length <= 36 &&
          !this.normalize(skill).includes('requisitos no estructurados')
      );
    return Array.from(
      new Set([...requirements, ...offer.matching_skills, ...offer.missing_skills])
    ).slice(0, 8);
  }

  recommendationReason(offer: FeedbackJob): string {
    const matching = offer.matching_skills.slice(0, 3);
    if (matching.length) {
      return `Tu experiencia en ${this.joinNaturally(matching)} encaja con requisitos relevantes del puesto.`;
    }
    return `La oferta mantiene una compatibilidad del ${Math.round(offer.final_score)}% con tu perfil.`;
  }

  private loadOffers(showLoader = true): void {
    this.isLoading = showLoader;
    this.errorMessage = '';
    this.feedbackService.listJobs().subscribe({
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
}
