import { AsyncPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import {
  LucideCircleAlert,
  LucideCircleCheck,
  LucideLoaderCircle,
  LucideMailCheck
} from '@lucide/angular';

import { AuthService } from './auth.service';

@Component({
  selector: 'app-verify-email',
  standalone: true,
  imports: [
    AsyncPipe,
    RouterLink,
    LucideCircleAlert,
    LucideCircleCheck,
    LucideLoaderCircle,
    LucideMailCheck
  ],
  templateUrl: './verify-email.component.html',
  styleUrl: './auth-page.scss'
})
export class VerifyEmailComponent implements OnInit {
  readonly user$ = this.authService.user$;
  state: 'verifying' | 'valid' | 'expired' | 'used' | 'invalid' = 'verifying';
  message = 'Estamos comprobando tu enlace de verificación.';
  isRedirecting = false;

  constructor(
    private readonly authService: AuthService,
    private readonly route: ActivatedRoute,
    private readonly router: Router
  ) {}

  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get('token');
    if (!token) {
      this.state = 'invalid';
      this.message = 'El enlace no contiene la información necesaria para verificar tu correo.';
      return;
    }

    this.authService.verifyEmail(token).subscribe({
      next: (response) => {
        this.state = 'valid';
        this.message = response.message || 'Tu correo se ha verificado correctamente.';
      },
      error: (error: HttpErrorResponse) => {
        if (error.status === 410) {
          this.state = 'expired';
          this.message = 'Este enlace ha caducado. Puedes solicitar uno nuevo.';
          return;
        }
        if (error.status === 409) {
          this.state = 'used';
          this.message = 'Este enlace ya se ha utilizado. Inicia sesión para continuar.';
          return;
        }

        this.state = 'invalid';
        this.message = 'El enlace no es válido. Comprueba que lo has abierto completo.';
      }
    });
  }

  goToLogin(): void {
    if (this.isRedirecting) {
      return;
    }

    this.isRedirecting = true;
    this.authService.logoutCurrentSession().subscribe({
      next: () => this.navigateToVerifiedLogin(),
      error: () => this.navigateToVerifiedLogin()
    });
  }

  private navigateToVerifiedLogin(): void {
    void this.router.navigate(['/login'], {
      queryParams: { reason: 'verified' }
    });
  }
}
