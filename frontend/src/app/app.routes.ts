import { Routes } from '@angular/router';

import { DashboardComponent } from './features/dashboard/dashboard.component';
import { JobsComponent } from './features/jobs/jobs.component';
import { LoginComponent } from './features/auth/login.component';
import { RegisterComponent } from './features/auth/register.component';
import { MatchingComponent } from './features/matching/matching.component';
import { ResumesComponent } from './features/resumes/resumes.component';

export const routes: Routes = [
  { path: '', component: DashboardComponent },
  { path: 'login', component: LoginComponent },
  { path: 'register', component: RegisterComponent },
  { path: 'resumes', component: ResumesComponent },
  { path: 'jobs', component: JobsComponent },
  { path: 'matching', component: MatchingComponent },
  { path: '**', redirectTo: '' }
];
