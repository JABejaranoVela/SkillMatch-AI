import { Component, OnInit } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { AuthService } from './auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './login.component.html',
  styleUrl: './auth-page.scss'
})
export class LoginComponent implements OnInit {
  errorMessage = '';
  accountMessage = '';
  isSubmitting = false;
  showPassword = false;

  readonly form = this.formBuilder.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required]]
  });

  constructor(
    private readonly formBuilder: FormBuilder,
    private readonly authService: AuthService,
    private readonly router: Router,
    private readonly route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    const reason = this.route.snapshot.queryParamMap.get('reason');
    if (reason === 'expired') {
      this.accountMessage = 'Tu sesión ha caducado. Inicia sesión para continuar.';
    } else if (reason === 'disabled') {
      this.accountMessage =
        'Tu cuenta está deshabilitada. Contacta con soporte si necesitas ayuda.';
    } else if (reason === 'verified') {
      this.accountMessage = 'Correo verificado. Ahora puedes iniciar sesión.';
    }
  }

  submit(): void {
    if (this.form.invalid || this.isSubmitting) {
      this.form.markAllAsTouched();
      return;
    }

    this.isSubmitting = true;
    this.errorMessage = '';
    const { email, password } = this.form.getRawValue();
    this.authService.login(email, password).subscribe({
      next: (user) => {
        this.isSubmitting = false;
        if (user.status === 'pending') {
          void this.router.navigateByUrl('/verify-email-sent');
          return;
        }
        const returnUrl = this.authService.safeReturnUrl(
          this.route.snapshot.queryParamMap.get('returnUrl')
        );
        void this.router.navigateByUrl(returnUrl);
      },
      error: (error) => {
        this.isSubmitting = false;
        if (error?.status === 403) {
          this.accountMessage =
            'Tu cuenta está deshabilitada. Contacta con soporte si necesitas ayuda.';
          return;
        }
        this.errorMessage = 'No hemos podido iniciar sesión con esos datos.';
      }
    });
  }
}
