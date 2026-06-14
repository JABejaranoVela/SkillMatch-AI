import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  LucideArrowRight,
  LucideBarChart3,
  LucideBookmark,
  LucideBriefcaseBusiness,
  LucideCheck,
  LucideCircle,
  LucideCloudUpload,
  LucideExternalLink,
  LucideFileText,
  LucideMapPin,
  LucideMonitor,
  LucideSearch,
  LucideSend,
  LucideStar,
  LucideUserRound
} from '@lucide/angular';

import { AuthService, AuthUser } from '../auth/auth.service';
import { FeedbackJob, FeedbackService } from '../feedback/feedback.service';
import { JobRecommendation, JobService } from '../jobs/job.service';
import { ProfessionalProfile, Resume, ResumeService } from '../resumes/resume.service';

interface NextStep {
  title: string;
  description: string;
  actionLabel: string;
  route: string;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    LucideArrowRight,
    LucideBarChart3,
    LucideBookmark,
    LucideBriefcaseBusiness,
    LucideCheck,
    LucideCircle,
    LucideCloudUpload,
    LucideExternalLink,
    LucideFileText,
    LucideMapPin,
    LucideMonitor,
    LucideSearch,
    LucideSend,
    LucideStar,
    LucideUserRound
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit {
  readonly user$ = this.authService.user$;

  activeResume: Resume | null = null;
  profile: ProfessionalProfile | null = null;
  recommendations: JobRecommendation[] = [];
  selectedOffers: FeedbackJob[] = [];
  totalRecommendations = 0;

  isResumeLoading = true;
  isProfileLoading = false;
  isRecommendationsLoading = false;
  isSelectedOffersLoading = true;
  resumeUnavailable = false;
  profileUnavailable = false;
  recommendationsUnavailable = false;
  selectedOffersUnavailable = false;

  constructor(
    private readonly authService: AuthService,
    private readonly feedbackService: FeedbackService,
    private readonly jobService: JobService,
    private readonly resumeService: ResumeService
  ) {}

  ngOnInit(): void {
    this.loadResume();
    this.loadSelectedOffers();
  }

  get nextStep(): NextStep {
    if (!this.activeResume) {
      return {
        title: 'Empieza subiendo tu CV',
        description:
          'Analizaremos tus habilidades, formación y experiencia para crear tu perfil profesional.',
        actionLabel: 'Subir mi CV',
        route: '/cv'
      };
    }

    if (this.activeResume.status !== 'processed') {
      return {
        title: 'Revisa tu CV',
        description:
          'Tu currículum todavía necesita revisión o procesamiento antes de buscar ofertas.',
        actionLabel: 'Ver mi CV',
        route: '/cv'
      };
    }

    return {
      title: 'Tu CV ya está analizado',
      description:
        'Hemos detectado tu perfil y habilidades principales. Explora ofertas compatibles con tu experiencia.',
      actionLabel: this.hasSelectedOffers ? 'Buscar más ofertas' : 'Buscar ofertas compatibles',
      route: '/jobs'
    };
  }

  get isResumeProcessed(): boolean {
    return this.activeResume?.status === 'processed';
  }

  get hasSelectedOffers(): boolean {
    return this.savedCount + this.appliedCount > 0;
  }

  get savedCount(): number {
    return this.selectedOffers.filter((offer) => offer.interaction_type === 'saved').length;
  }

  get appliedCount(): number {
    return this.selectedOffers.filter((offer) => offer.interaction_type === 'applied').length;
  }

  get hasDetectedSkills(): boolean {
    if (!this.profile) {
      return false;
    }

    if ((this.profile.technologies?.length ?? 0) > 0) {
      return true;
    }

    const categories = this.profile.analysis?.skill_categories ?? {};
    return Object.values(categories).some((skills) => skills.length > 0);
  }

  get profileName(): string {
    return (
      this.profile?.profile_type ||
      this.profile?.analysis?.primary_profile?.name ||
      'Pendiente de análisis'
    );
  }

  displayName(user: AuthUser): string {
    const fullName = user.full_name?.trim();
    return fullName || user.email.split('@')[0] || 'usuario';
  }

  resumeStatusLabel(status?: string): string {
    const labels: Record<string, string> = {
      processed: 'Analizado',
      pending: 'Pendiente',
      processing: 'Procesando',
      failed: 'Fallido'
    };
    return status ? labels[status] ?? 'Pendiente' : 'Sin CV';
  }

  resumeStatusClass(status?: string): string {
    if (status === 'processed') {
      return 'status-success';
    }
    if (status === 'failed') {
      return 'status-warning';
    }
    return 'status-neutral';
  }

  resumeUpdatedLabel(): string {
    if (!this.activeResume) {
      return 'Sube un CV para comenzar';
    }

    const sourceDate = this.activeResume.processed_at || this.activeResume.created_at;
    const timestamp = new Date(sourceDate).getTime();
    if (Number.isNaN(timestamp)) {
      return 'Fecha no disponible';
    }

    const elapsedDays = Math.max(0, Math.floor((Date.now() - timestamp) / 86_400_000));
    if (elapsedDays === 0) {
      return 'Actualizado hoy';
    }
    if (elapsedDays === 1) {
      return 'Actualizado ayer';
    }
    return `Actualizado hace ${elapsedDays} días`;
  }

  compatibilityScore(recommendation: JobRecommendation): number {
    return Math.round(recommendation.final_score);
  }

  companyInitials(company: string | null): string {
    if (!company?.trim()) {
      return 'OF';
    }
    return company
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((word) => word.charAt(0))
      .join('')
      .toUpperCase();
  }

  openOffer(recommendation: JobRecommendation): void {
    if (!recommendation.job.url) {
      return;
    }
    window.open(recommendation.job.url, '_blank', 'noopener,noreferrer');
  }

  private loadResume(): void {
    this.resumeService.list().subscribe({
      next: (resumes) => {
        this.activeResume = resumes.find((resume) => resume.is_active) ?? resumes[0] ?? null;
        this.isResumeLoading = false;
        if (this.isResumeProcessed) {
          this.loadProfile();
          this.loadRecommendations();
        }
      },
      error: () => {
        this.resumeUnavailable = true;
        this.isResumeLoading = false;
      }
    });
  }

  private loadProfile(): void {
    this.isProfileLoading = true;
    this.resumeService.getActiveProfile().subscribe({
      next: (profile) => {
        this.profile = profile;
        this.isProfileLoading = false;
      },
      error: () => {
        this.profileUnavailable = true;
        this.isProfileLoading = false;
      }
    });
  }

  private loadRecommendations(): void {
    this.isRecommendationsLoading = true;
    this.jobService.recommended(3, 0).subscribe({
      next: (page) => {
        this.recommendations = page.items.slice(0, 3);
        this.totalRecommendations = page.total;
        this.isRecommendationsLoading = false;
      },
      error: () => {
        this.recommendationsUnavailable = true;
        this.isRecommendationsLoading = false;
      }
    });
  }

  private loadSelectedOffers(): void {
    this.feedbackService.listJobs().subscribe({
      next: (offers) => {
        this.selectedOffers = offers;
        this.isSelectedOffersLoading = false;
      },
      error: () => {
        this.selectedOffersUnavailable = true;
        this.isSelectedOffersLoading = false;
      }
    });
  }
}
