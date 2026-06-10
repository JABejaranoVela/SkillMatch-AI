import { Routes } from '@angular/router';

import { DashboardComponent } from './features/dashboard/dashboard.component';
import { LandingComponent } from './features/landing/landing.component';
import { JobsComponent } from './features/jobs/jobs.component';
import { LoginComponent } from './features/auth/login.component';
import { RegisterComponent } from './features/auth/register.component';
import { VerifyEmailComponent } from './features/auth/verify-email.component';
import { VerificationSentComponent } from './features/auth/verification-sent.component';
import { ResumesComponent } from './features/resumes/resumes.component';
import { SavedJobsComponent } from './features/saved-jobs/saved-jobs.component';
import { ProfileComponent } from './features/profile/profile.component';
import { SettingsComponent } from './features/settings/settings.component';
import { pendingGuard, verifiedGuard } from './core/auth.guard';

export const routes: Routes = [
  { path: '', component: LandingComponent },
  { path: 'login', component: LoginComponent },
  { path: 'register', component: RegisterComponent },
  { path: 'verify-email', component: VerifyEmailComponent },
  {
    path: 'verify-email-sent',
    component: VerificationSentComponent,
    canActivate: [pendingGuard]
  },
  { path: 'dashboard', component: DashboardComponent, canActivate: [verifiedGuard] },
  { path: 'resumes', component: ResumesComponent, canActivate: [verifiedGuard] },
  { path: 'cv', redirectTo: 'resumes', pathMatch: 'full', canActivate: [verifiedGuard] },
  { path: 'jobs', component: JobsComponent, canActivate: [verifiedGuard] },
  { path: 'my-jobs', component: SavedJobsComponent, canActivate: [verifiedGuard] },
  {
    path: 'saved-jobs',
    redirectTo: 'my-jobs',
    pathMatch: 'full',
    canActivate: [verifiedGuard]
  },
  { path: 'profile', component: ProfileComponent, canActivate: [verifiedGuard] },
  { path: 'settings', component: SettingsComponent, canActivate: [verifiedGuard] },
  { path: '**', redirectTo: '' }
];
