import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
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
    RouterLink,
    LucideCircleAlert,
    LucideCircleCheck,
    LucideLoaderCircle,
    LucideMailCheck
  ],
  templateUrl: './verify-email.component.html',
  styleUrl: './verify-email.component.scss'
})
export class VerifyEmailComponent implements OnInit {
  state: 'verifying' | 'valid' | 'expired' | 'invalid' = 'verifying';
  message = 'Estamos comprobando tu enlace de verificacion.';

  constructor(
    private readonly authService: AuthService,
    private readonly route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get('token');
    if (!token) {
      this.state = 'invalid';
      this.message = 'El enlace de verificacion no contiene un token valido.';
      return;
    }

    this.authService.verifyEmail(token).subscribe({
      next: (response) => {
        this.state = 'valid';
        this.message = response.message;
      },
      error: (error) => {
        const detail = String(error?.error?.detail || '');
        if (error?.status === 410) {
          this.state = 'expired';
          this.message = 'Este enlace ha caducado. Inicia sesion para solicitar otro.';
          return;
        }
        this.state = 'invalid';
        this.message = detail || 'El enlace no es valido o ya ha sido utilizado.';
      }
    });
  }
}
