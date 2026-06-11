import { Component, OnInit } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { AuthService } from './auth.service';

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './reset-password.component.html',
  styleUrl: './auth-page.scss'
})
export class ResetPasswordComponent implements OnInit {
  state: 'ready' | 'sending' | 'success' | 'invalid' | 'expired' | 'used' = 'ready';
  message = '';
  token = '';
  showNewPassword = false;
  showConfirmation = false;

  readonly form = this.formBuilder.nonNullable.group({
    newPassword: [
      '',
      [Validators.required, Validators.minLength(10), Validators.maxLength(128)]
    ],
    confirmPassword: [
      '',
      [Validators.required, Validators.minLength(10), Validators.maxLength(128)]
    ]
  });

  constructor(
    private readonly formBuilder: FormBuilder,
    private readonly authService: AuthService,
    private readonly route: ActivatedRoute
  ) {
    this.form.controls.confirmPassword.valueChanges.subscribe(() => {
      const errors = this.form.controls.confirmPassword.errors;
      if (!errors?.['mismatch']) {
        return;
      }
      const { mismatch: _mismatch, ...remainingErrors } = errors;
      this.form.controls.confirmPassword.setErrors(
        Object.keys(remainingErrors).length ? remainingErrors : null
      );
    });
  }

  ngOnInit(): void {
    this.token = this.route.snapshot.queryParamMap.get('token') || '';
    if (!this.token) {
      this.state = 'invalid';
      this.message = 'El enlace no es válido o ha caducado.';
    }
  }

  submit(): void {
    if (!this.token || this.form.invalid || this.state === 'sending') {
      this.form.markAllAsTouched();
      return;
    }

    const values = this.form.getRawValue();
    if (values.newPassword !== values.confirmPassword) {
      this.form.controls.confirmPassword.setErrors({ mismatch: true });
      return;
    }

    this.state = 'sending';
    this.message = '';
    this.authService.resetPassword(
      this.token,
      values.newPassword,
      values.confirmPassword
    ).subscribe({
      next: (response) => {
        this.state = 'success';
        this.message = response.message;
        this.form.reset();
      },
      error: (error) => {
        if (error?.status === 410) {
          this.state = 'expired';
        } else if (error?.status === 409) {
          this.state = 'used';
        } else {
          this.state = 'invalid';
        }
        this.message = 'El enlace no es válido o ha caducado.';
      }
    });
  }
}
