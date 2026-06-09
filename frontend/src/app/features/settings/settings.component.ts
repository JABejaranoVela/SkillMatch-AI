import { Component } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { LucideKeyRound, LucideLogOut, LucideSave, LucideShieldCheck } from '@lucide/angular';

import { AuthService } from '../auth/auth.service';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    LucideKeyRound,
    LucideLogOut,
    LucideSave,
    LucideShieldCheck
  ],
  templateUrl: './settings.component.html',
  styleUrl: '../profile/account-page.scss'
})
export class SettingsComponent {
  isSaving = false;
  statusMessage = '';
  errorMessage = '';

  readonly form = this.formBuilder.nonNullable.group({
    currentPassword: ['', [Validators.required, Validators.minLength(8)]],
    newPassword: ['', [Validators.required, Validators.minLength(8)]],
    confirmPassword: ['', [Validators.required, Validators.minLength(8)]]
  });

  constructor(
    private readonly formBuilder: FormBuilder,
    private readonly authService: AuthService
  ) {}

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    const values = this.form.getRawValue();
    if (values.newPassword !== values.confirmPassword) {
      this.errorMessage = 'Las nuevas contraseñas no coinciden.';
      return;
    }
    if (values.currentPassword === values.newPassword) {
      this.errorMessage = 'La nueva contraseña debe ser diferente de la actual.';
      return;
    }

    this.isSaving = true;
    this.statusMessage = '';
    this.errorMessage = '';
    this.authService.changePassword(values.currentPassword, values.newPassword).subscribe({
      next: () => {
        this.isSaving = false;
        this.statusMessage = 'Contraseña actualizada correctamente.';
        this.form.reset();
      },
      error: (error) => {
        this.isSaving = false;
        this.errorMessage =
          error?.error?.detail || 'No se pudo actualizar la contraseña.';
      }
    });
  }

  logout(): void {
    this.authService.logout();
  }
}
