import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Subscription } from 'rxjs';
import { LucideAtSign, LucideSave, LucideShieldCheck, LucideUserRound } from '@lucide/angular';

import { AuthService, AuthUser } from '../auth/auth.service';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    LucideAtSign,
    LucideSave,
    LucideShieldCheck,
    LucideUserRound
  ],
  templateUrl: './profile.component.html',
  styleUrl: './account-page.scss'
})
export class ProfileComponent implements OnInit, OnDestroy {
  user: AuthUser | null = null;
  isSaving = false;
  statusMessage = '';
  errorMessage = '';

  readonly form = this.formBuilder.nonNullable.group({
    fullName: ['', [Validators.required, Validators.maxLength(255)]]
  });

  private userSubscription: Subscription | null = null;

  constructor(
    private readonly formBuilder: FormBuilder,
    private readonly authService: AuthService
  ) {}

  ngOnInit(): void {
    this.userSubscription = this.authService.user$.subscribe((user) => {
      this.user = user;
      if (user) {
        this.form.patchValue({ fullName: user.full_name ?? '' }, { emitEvent: false });
      }
    });
  }

  ngOnDestroy(): void {
    this.userSubscription?.unsubscribe();
  }

  get initials(): string {
    const source = this.user?.full_name?.trim() || this.user?.email || 'Usuario';
    const parts = source.split(/\s+/).filter(Boolean);
    return parts.slice(0, 2).map((part) => part[0]).join('').toUpperCase();
  }

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.isSaving = true;
    this.statusMessage = '';
    this.errorMessage = '';
    this.authService.updateProfile(this.form.getRawValue().fullName.trim()).subscribe({
      next: () => {
        this.isSaving = false;
        this.statusMessage = 'Perfil actualizado correctamente.';
        this.form.markAsPristine();
      },
      error: () => {
        this.isSaving = false;
        this.errorMessage = 'No se pudo actualizar el perfil.';
      }
    });
  }
}
