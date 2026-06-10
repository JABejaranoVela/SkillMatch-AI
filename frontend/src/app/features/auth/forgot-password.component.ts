import { Component } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AuthService } from './auth.service';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './forgot-password.component.html',
  styleUrl: './login.component.scss'
})
export class ForgotPasswordComponent {
  state: 'idle' | 'sending' | 'sent' | 'error' = 'idle';
  message = '';

  readonly form = this.formBuilder.nonNullable.group({
    email: ['', [Validators.required, Validators.email]]
  });

  constructor(
    private readonly formBuilder: FormBuilder,
    private readonly authService: AuthService
  ) {}

  submit(): void {
    if (this.form.invalid || this.state === 'sending') {
      this.form.markAllAsTouched();
      return;
    }

    this.state = 'sending';
    this.message = '';
    this.authService.forgotPassword(this.form.getRawValue().email).subscribe({
      next: (response) => {
        this.state = 'sent';
        this.message = response.message;
      },
      error: () => {
        this.state = 'error';
        this.message = 'No se pudo procesar la solicitud. Intentalo de nuevo mas tarde.';
      }
    });
  }
}
