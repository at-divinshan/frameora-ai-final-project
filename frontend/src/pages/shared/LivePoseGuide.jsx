import { Camera, Sparkles } from 'lucide-react';
import useAuth from '../../hooks/useAuth';
import DashboardLayout from '../../components/layout/DashboardLayout';
import OwnerLayout from '../../components/layout/OwnerLayout';
import '../../styles/pose-coming-soon.css';

export default function LivePoseGuide(){
  const {user}=useAuth();
  const Layout=user.role==='owner'?OwnerLayout:DashboardLayout;
  return <Layout><section className="pose-coming-soon" aria-labelledby="pose-coming-title">
    <div className="pose-coming-art" aria-hidden="true"><Camera size={76} strokeWidth={1.5}/><Sparkles className="pose-coming-spark" size={28}/></div>
    <span className="pose-coming-status">Coming Soon ✨</span>
    <h1 id="pose-coming-title">Something Exciting is Coming! 🚀</h1>
    <p>Our AI Live Pose Guide is getting ready to make your photoshoots even more amazing!</p>
    <footer>Stay tuned. The perfect pose is on its way! 📸</footer>
  </section></Layout>;
}
