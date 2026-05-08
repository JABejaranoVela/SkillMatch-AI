import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { FeedbackService, InteractionType } from '../feedback/feedback.service';
import { Resume, ResumeService } from '../resumes/resume.service';
import { MatchResult, MatchingService } from './matching.service';

@Component({
  selector: 'app-matching',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './matching.component.html',
  styleUrl: '../resumes/resumes.component.scss'
})
export class MatchingComponent implements OnInit {
  resumeId: number | null = null;
  resumes: Resume[] = [];
  results: MatchResult[] = [];
  statusMessage = '';

  get activeResumeLabel(): string {
    return this.resumes.length ? this.resumes[0].filename : 'No hay CV activo';
  }

  constructor(
    private readonly matchingService: MatchingService,
    private readonly feedbackService: FeedbackService,
    private readonly resumeService: ResumeService
  ) {}

  ngOnInit(): void {
    this.resumeService.list().subscribe({
      next: (resumes) => {
        this.resumes = resumes;
        const processedResume = resumes.find((resume) => resume.status === 'processed');
        this.resumeId = processedResume?.id ?? resumes[0]?.id ?? null;
      }
    });
  }

  runMatching(): void {
    if (!this.resumes.length) {
      this.statusMessage = 'Sube y procesa un CV antes de calcular matching.';
      return;
    }

    this.statusMessage = 'Calculando ranking explicable con las ofertas disponibles...';
    this.matchingService.runActive().subscribe({
      next: (results) => {
        this.results = results;
        this.statusMessage = `Ranking generado con ${results.length} ofertas.`;
      },
      error: () => {
        this.statusMessage = 'No se pudo calcular el matching.';
      }
    });
  }

  sendFeedback(result: MatchResult, interactionType: InteractionType): void {
    this.feedbackService.create(result.job_id, interactionType, result.id).subscribe({
      next: () => {
        this.statusMessage = `Feedback registrado: ${interactionType}.`;
      },
      error: () => {
        this.statusMessage = 'No se pudo registrar el feedback.';
      }
    });
  }

  scoreLabel(result: MatchResult): string {
    return `Skills ${result.rules_score}% + IA semantica ${result.semantic_score}%`;
  }
}
