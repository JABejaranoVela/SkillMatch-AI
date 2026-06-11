import { Component } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from './auth.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './register.component.html',
  styleUrl: './auth-page.scss'
})
export class RegisterComponent {
  errorMessage = '';
  isSubmitting = false;
  showPassword = false;
  showConfirmation = false;

  readonly form = this.formBuilder.nonNullable.group({
    fullName: ['', [Validators.required, Validators.maxLength(255)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(10), Validators.maxLength(128)]],
    confirmPassword: ['', [Validators.required]]
  });

  constructor(
    private readonly formBuilder: FormBuilder,
    private readonly authService: AuthService,
    private readonly router: Router
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

  submit(): void {
    if (this.form.invalid || this.isSubmitting) {
      this.form.markAllAsTouched();
      return;
    }
    const values = this.form.getRawValue();
    if (values.password !== values.confirmPassword) {
      this.form.controls.confirmPassword.setErrors({ mismatch: true });
      return;
    }

    this.isSubmitting = true;
    this.errorMessage = '';
    this.authService.register(values.email, values.password, values.fullName).subscribe({
      next: () => {
        this.isSubmitting = false;
        void this.router.navigateByUrl('/verify-email-sent');
      },
      error: () => {
        this.isSubmitting = false;
        this.errorMessage = 'No hemos podido crear la cuenta. Inténtalo de nuevo.';
      }
    });
  }
}
