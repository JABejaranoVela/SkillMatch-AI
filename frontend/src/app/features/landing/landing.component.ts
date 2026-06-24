import { AsyncPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, ElementRef, ViewChild } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  LucideArrowRight,
  LucideBarChart3,
  LucideBrainCircuit,
  LucideBriefcaseBusiness,
  LucideCheck,
  LucideChevronRight,
  LucideCircleCheck,
  LucideCloudUpload,
  LucideFileSearch,
  LucideFileText,
  LucideGraduationCap,
  LucideLanguages,
  LucideMenu,
  LucidePlay,
  LucideSearch,
  LucideShieldCheck,
  LucideSparkles,
  LucideTarget,
  LucideUserRound,
  LucideX
} from '@lucide/angular';

import { AuthService } from '../auth/auth.service';
import { RevealOnScrollDirective } from '../../shared/directives/reveal-on-scroll.directive';
import { PublicDemoAnalysis, PublicDemoService } from './public-demo.service';

type DemoState = 'idle' | 'selected' | 'loading' | 'success' | 'error';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [
    AsyncPipe,
    RouterLink,
    LucideArrowRight,
    LucideBarChart3,
    LucideBrainCircuit,
    LucideBriefcaseBusiness,
    LucideCheck,
    LucideChevronRight,
    LucideCircleCheck,
    LucideCloudUpload,
    LucideFileSearch,
    LucideFileText,
    LucideGraduationCap,
    LucideLanguages,
    LucideMenu,
    LucidePlay,
    LucideSearch,
    LucideShieldCheck,
    LucideSparkles,
    LucideTarget,
    LucideUserRound,
    LucideX,
    RevealOnScrollDirective
  ],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.scss'
})
export class LandingComponent {
  @ViewChild('demoFileInput') private demoFileInput?: ElementRef<HTMLInputElement>;

  readonly authenticated$ = this.authService.authenticated$;
  mobileMenuOpen = false;
  demoState: DemoState = 'idle';
  demoFile: File | null = null;
  demoResult: PublicDemoAnalysis | null = null;
  demoError = '';
  demoDragActive = false;

  constructor(
    private readonly authService: AuthService,
    private readonly publicDemoService: PublicDemoService
  ) {}

  closeMenu(): void {
    this.mobileMenuOpen = false;
  }

  toggleMenu(): void {
    this.mobileMenuOpen = !this.mobileMenuOpen;
  }

  onDemoFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectDemoFile(input.files?.[0] ?? null);
  }

  onDemoDragOver(event: DragEvent): void {
    event.preventDefault();
    if (this.demoState !== 'loading') {
      this.demoDragActive = true;
    }
  }

  onDemoDragLeave(event: DragEvent): void {
    event.preventDefault();
    this.demoDragActive = false;
  }

  onDemoDrop(event: DragEvent): void {
    event.preventDefault();
    this.demoDragActive = false;
    if (this.demoState !== 'loading') {
      this.selectDemoFile(event.dataTransfer?.files?.[0] ?? null);
    }
  }

  analyzeDemoCv(): void {
    if (!this.demoFile || this.demoState === 'loading') {
      return;
    }

    this.demoState = 'loading';
    this.demoError = '';
    this.demoResult = null;
    this.publicDemoService.analyzeCv(this.demoFile).subscribe({
      next: (result) => {
        this.demoResult = result;
        this.demoState = 'success';
      },
      error: (error: HttpErrorResponse) => {
        this.demoError = this.demoErrorMessage(error);
        this.demoState = 'error';
      }
    });
  }

  resetDemo(): void {
    this.demoState = 'idle';
    this.demoFile = null;
    this.demoResult = null;
    this.demoError = '';
    this.demoDragActive = false;
    if (this.demoFileInput) {
      this.demoFileInput.nativeElement.value = '';
    }
  }

  formatFileSize(size: number): string {
    return `${(size / (1024 * 1024)).toFixed(2)} MB`;
  }

  private selectDemoFile(file: File | null): void {
    this.demoResult = null;
    this.demoError = '';
    if (!file) {
      this.resetDemo();
      return;
    }

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      this.demoFile = null;
      this.demoState = 'error';
      this.demoError = 'Selecciona un archivo PDF válido.';
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      this.demoFile = null;
      this.demoState = 'error';
      this.demoError = 'El PDF supera el tamaño máximo de 10 MB.';
      return;
    }

    this.demoFile = file;
    this.demoState = 'selected';
  }

  private demoErrorMessage(error: HttpErrorResponse): string {
    if (error.status === 413) {
      return 'El PDF supera el tamaño máximo permitido.';
    }
    if (error.status === 429) {
      return 'Has alcanzado el límite temporal de análisis. Inténtalo de nuevo más tarde.';
    }
    if (error.status === 400 && typeof error.error?.detail === 'string') {
      return error.error.detail;
    }
    return 'No hemos podido analizar el CV en este momento. Inténtalo de nuevo.';
  }
}
