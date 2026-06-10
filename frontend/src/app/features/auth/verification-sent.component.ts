import { AsyncPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component } from '@angular/core';
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
  styleUrl: './verify-email.component.scss'
})
export class VerificationSentComponent {
  readonly user$ = this.authService.user$;
  state: 'idle' | 'sending' | 'sent' | 'cooldown' | 'error' = 'idle';
  message = '';

  constructor(private readonly authService: AuthService) {}

  resend(): void {
    if (this.state === 'sending') {
      return;
    }
    this.state = 'sending';
    this.message = '';
    this.authService.resendVerification().subscribe({
      next: (response) => {
        this.state = 'sent';
        this.message = response.message;
      },
      error: (error: HttpErrorResponse) => {
        if (error.status === 429) {
          const retryAfter = error.headers.get('Retry-After');
          this.state = 'cooldown';
          this.message = retryAfter
            ? `Espera ${retryAfter} segundos antes de volver a intentarlo.`
            : 'Espera un minuto antes de volver a intentarlo.';
          return;
        }
        this.state = 'error';
        this.message = 'No se pudo enviar el correo. Intentalo de nuevo mas tarde.';
      }
    });
  }

  logout(): void {
    this.authService.logout();
  }
}
