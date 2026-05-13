import { Route, Router } from "@/lib/router";
import { CompanyPage } from "@/pages/CompanyPage";
import { DiscoverPage } from "@/pages/DiscoverPage";
import { HelloPage } from "@/pages/HelloPage";
import { NetworkPage } from "@/pages/NetworkPage";
import { PersonPage } from "@/pages/PersonPage";

// URL hierarchy mirrors the spike (see design.md §前端架构):
//   #/                         → hello / discover landing
//   #/discover                 → DiscoverPage
//   #/p/<name>[/<bucket>]      → PersonPage (hub vs entity is one component)
//   #/c/<stock_code>           → CompanyPage
//   #/n/<name>                 → NetworkPage (ego)
export function App() {
  return (
    <Router defaultPath="/">
      <Route path="/" component={HelloPage} />
      <Route path="/discover" component={DiscoverPage} />
      <Route path="/p/:name" component={PersonPage} />
      <Route path="/p/:name/:bucket" component={PersonPage} />
      <Route path="/c/:code" component={CompanyPage} />
      <Route path="/n/:name" component={NetworkPage} />
    </Router>
  );
}
