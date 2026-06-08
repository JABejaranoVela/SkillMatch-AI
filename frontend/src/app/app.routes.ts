import { Routes } from '@angular/router';

import { DashboardComponent } from './features/dashboard/dashboard.component';
import { JobsComponent } from './features/jobs/jobs.component';
import { LoginComponent } from './features/auth/login.component';
import { RegisterComponent } from './features/auth/register.component';
import { ResumesComponent } from './features/resumes/resumes.component';
import { SavedJobsComponent } from './features/saved-jobs/saved-jobs.component';

export const routes: Routes = [
  { path: '', component: DashboardComponent },
  { path: 'login', component: LoginComponent },
  { path: 'register', component: RegisterComponent },
  { path: 'resumes', component: ResumesComponent },
  { path: 'jobs', component: JobsComponent },
  { path: 'my-jobs', component: SavedJobsComponent },
  { path: '**', redirectTo: '' }
];
