import { AsyncPipe } from '@angular/common';
import { Component } from '@angular/core';
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
    LucideLanguages,
    LucideMenu,
    LucidePlay,
    LucideSearch,
    LucideShieldCheck,
    LucideSparkles,
    LucideTarget,
    LucideUserRound,
    LucideX
  ],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.scss'
})
export class LandingComponent {
  readonly authenticated$ = this.authService.authenticated$;
  mobileMenuOpen = false;

  constructor(private readonly authService: AuthService) {}

  closeMenu(): void {
    this.mobileMenuOpen = false;
  }

  toggleMenu(): void {
    this.mobileMenuOpen = !this.mobileMenuOpen;
  }
}
