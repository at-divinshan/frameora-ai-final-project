import { CalendarDays, Sparkles, Image, FolderHeart, BriefcaseBusiness, ShieldCheck, Link2Off, UserRound, SunMoon } from "lucide-react";
export const features = [
  { id: 'planning', icon: CalendarDays, title: 'Photography Plan Management', short: 'Photoshoot Planning', description: 'Bring occasions, locations, dates and equipment into one photography plan.', benefit: 'Arrive with a clear direction and more room to create.' },
  { id: 'suggestions', icon: Sparkles, title: 'AI Photography Suggestions', short: 'AI Photography Suggestions', description: 'Explore personalized poses, camera angles, outfits, locations and themes based on your requirements.', benefit: 'Find a fresh starting point when inspiration feels out of reach.' },
  { id: 'generation', icon: Image, title: 'AI Image Generation', short: 'AI Image Generation', description: 'Turn a photography idea into a visual concept before your shoot.', benefit: 'Explore mood and composition before picking up your camera.' },
  { id: 'gallery', icon: FolderHeart, title: 'Personal Gallery Management', description: 'Save and organize photography images and generated concepts in your personal gallery.', benefit: 'Keep the ideas you love close to the plans they inspire.' },
  { id: 'projects', icon: BriefcaseBusiness, title: 'Studio Owner Project Management', short: 'Studio Project Sharing', description: 'Create customer projects, upload images and keep each shoot organized in your studio workspace.', benefit: 'Give every customer project its own clear home.' },
  { id: 'sharing', icon: ShieldCheck, title: 'Authenticated Customer Photo Sharing', description: 'Share a secure link to photos inside Frameora AI. Customers must log in or register before viewing permitted images.', benefit: 'Keep customer photography behind authenticated, authorized access.' },
  { id: 'deactivation', icon: Link2Off, title: 'Secure Sharing Link Deactivation', description: 'Manage sharing links and deactivate access when a project no longer needs to be shared.', benefit: 'Stay in control of when customer images are accessible.' },
  { id: 'profile', icon: UserRound, title: 'User Profiles and Settings', description: 'Manage your profile and photography preferences from your account workspace.', benefit: 'Make your creative workspace feel personal.' },
  { id: 'theme', icon: SunMoon, title: 'Light/Dark Theme Support', description: 'Switch between deep navy and soft light surfaces. Your theme choice carries across the website.', benefit: 'Choose the view that feels right for you.', live: true },
];
export const creatorJourney = [
  ['Create your account', 'Register with email and password or Google. Choose the Normal User role.', true],
  ['Log in securely', 'Use your email and password or your connected Google account.', true],
  ['Open your dashboard', 'Enter your personal dashboard from your account.', true],
  ['Create a photography plan', 'Start with an occasion, location and date.'],
  ['Add your requirements', 'Describe your preferred mood, outfits, equipment and creative goals.'],
  ['Discover AI suggestions', 'Explore personalized poses, angles, locations and themes.'],
  ['Visualize your ideas', 'Explore AI-generated concepts to guide your photography.'],
  ['Organize your gallery', 'Save your images and visual inspiration in one place.'],
  ['Make it yours', 'Manage your profile, preferences and account settings.'],
];
export const studioJourney = [
  ['Join as a Studio Owner', 'Register or log in with your Studio Owner account.', true],
  ['Open your studio dashboard', 'Access your role-specific studio workspace.', true],
  ['Create a customer project', 'Give each photography assignment its own project.'],
  ['Upload and organize images', 'Keep customer photos together within the right project.'],
  ['Generate a secure sharing link', 'Create a controlled link for the project images.'],
  ['Share with your customer', 'Send the project link to the intended customer.'],
  ['Customer signs in', 'Customers log in or register before viewing. Already signed-in customers continue directly to the authorized preview.'],
  ['View permitted images', 'Customers see only authorized project images inside Frameora AI. No separate customer role is needed.'],
  ['Control ongoing access', 'Activate sharing when ready and deactivate the link when access should end.'],
];
export const commonFaq = [
  ['What is Frameora AI?', 'Frameora AI is a photography platform combining working account access and role-based dashboards with planned tools for photography planning, AI inspiration, galleries and studio projects.'],
  ['Who can use Frameora AI?', 'Photography enthusiasts and creators can register as Normal Users. Professional studios can register as Studio Owners. Admin registration is not publicly available.'],
  ['Can I sign up with Google or email?', 'Yes. Email/password registration and login, Google sign-in, Google registration and Google account linking are supported.'],
  ['Which photography features are available?', 'Account authentication, role-based dashboard access and light/dark themes are available. Photography planning, AI suggestions, image generation, galleries, studio projects and sharing are planned.'],
  ['Does my theme choice carry across pages?', 'Yes. Light and dark modes use the same theme setting across the public website and existing account pages.'],
];
export const studioFaq = [
  ['How will studios share customer photos?', 'The planned workflow lets Studio Owners create projects, upload customer images and share secure links to protected previews inside Frameora AI.'],
  ['Do customers need an account to view photos?', 'Yes. The planned sharing flow requires login or registration, followed by authorization to view the project. Signed-in customers go directly to the authorized preview without extra Login/Register prompts. There is no separate public customer role.'],
  ['Can a Studio Owner deactivate a sharing link?', 'Yes, link activation and deactivation are part of the planned studio workflow. These controls are not yet available.'],
];
