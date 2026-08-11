import { Component } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { ReactiveFormsModule, FormGroup, FormControl } from "@angular/forms";

@Component({
  selector: "app-home",
  template: `<form><input formControlName="name" /></form>`,
})
export class HomeComponent {
  form = new FormGroup({ name: new FormControl("") });

  constructor(private http: HttpClient) {}

  submit() {
    this.http.post("/api/greet", this.form.value).subscribe();
  }
}
