import { AsyncPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  LucideLoaderCircle,
  LucideLogOut,
  LucideMailCheck,
  LucideRefreshCw
} from '@lucide/angular';

import { AuthService } from './auth.service';

@Component({
  selector: 'app-verification-sent',
  standalone: true,
  imports: [
    AsyncPipe,
    RouterLink,
    LucideLoaderCircle,
    LucideLogOut,
    LucideMailCheck,
    LucideRefreshCw
  ],
  templateUrl: './verification-sent.component.html',
  styleUrl: './auth-page.scss'
})
export class VerificationSentComponent implements OnDestroy {
  readonly user$ = this.authService.user$;
  state: 'idle' | 'sending' | 'sent' | 'error' = 'idle';
  message = '';
  cooldownSeconds = 0;
  private cooldownTimer: ReturnType<typeof setInterval> | null = null;

  constructor(private readonly authService: AuthService) {}

  ngOnDestroy(): void {
    this.clearCooldown();
  }

  resend(): void {
    if (this.state === 'sending' || this.cooldownSeconds > 0) {
      return;
    }

    this.state = 'sending';
    this.message = '';
    this.authService.resendVerification().subscribe({
      next: (response) => {
        this.state = 'sent';
        this.message = response.message || 'Hemos enviado un nuevo correo de verificación.';
        this.startCooldown(60);
      },
      error: (error: HttpErrorResponse) => {
        if (error.status === 429) {
          const retryAfter = Number(error.headers.get('Retry-After'));
          this.state = 'idle';
          this.message = 'Espera a que termine la cuenta atrás para volver a intentarlo.';
          this.startCooldown(Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : 60);
          return;
        }

        this.state = 'error';
        this.message = 'No hemos podido enviar el correo. Inténtalo de nuevo más tarde.';
      }
    });
  }

  logout(): void {
    this.authService.logout();
  }

  private startCooldown(seconds: number): void {
    this.clearCooldown();
    this.cooldownSeconds = Math.ceil(seconds);
    this.cooldownTimer = setInterval(() => {
      this.cooldownSeconds = Math.max(0, this.cooldownSeconds - 1);
      if (this.cooldownSeconds === 0) {
        this.clearCooldown();
      }
    }, 1000);
  }

  private clearCooldown(): void {
    if (this.cooldownTimer !== null) {
      clearInterval(this.cooldownTimer);
      this.cooldownTimer = null;
    }
  }
}
