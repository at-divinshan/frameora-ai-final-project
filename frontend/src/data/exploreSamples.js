// Add the original image and one entry here. Descriptions are editorial guidance,
// not a claim about the location, identity, or technical settings of a photo.
export const exploreSamples = [
  {id:'birthday-01', category:'Birthday', title:'Lavender Garden Birthday', people:1, environment:'Outdoor',
    pose:'Stand at a gentle three-quarter angle, hold a small bouquet at waist level and look back toward the camera.',
    background:'Garden birthday setup with lavender and white balloons, a cake table and warm string lights.',
    camera:'Eye-level waist-up portrait with the decorated table to one side.', lighting:'Soft late-afternoon daylight with warm fairy-light accents.',
    style:'Natural', lightingPreference:'Golden Hour', posePreference:'Natural', angle:'Eye Level', clothing:'Formal', colors:'Lavender',
    outfit:'Lavender puff-sleeve dress and a small white-flower bouquet.', instructions:'Keep the balloon arch and cake softly recognizable behind the subject; retain a relaxed smile and gentle garden depth.'},
  {id:'birthday-02', category:'Birthday', title:'Relaxed Birthday Picnic', people:1, environment:'Outdoor',
    pose:'Sit on a picnic blanket with one knee raised, rest a forearm on that knee and look slightly off-camera.',
    background:'Garden picnic with a low wooden cake display, wrapped gifts, purple balloons and a glowing birthday sign.',
    camera:'Eye-level seated portrait, wide enough to include the picnic decorations.', lighting:'Warm late-afternoon garden light and soft decorative bulbs.',
    style:'Natural', lightingPreference:'Golden Hour', posePreference:'Candid', angle:'Eye Level', clothing:'Casual', colors:'White and beige',
    outfit:'Open-collar white shirt, beige trousers and clean white sneakers.', instructions:'Keep the seated pose relaxed and include gifts and cake beside the subject without obscuring their hands.'},
  {id:'prewedding-01', category:'Pre-wedding', title:'Under the Floral Arch', people:2, environment:'Outdoor',
    pose:'Stand close together beneath the flowers; one partner gently holds the other at the waist while they turn toward each other.',
    background:'Leafy garden wedding arch with pale flowers and flowing white fabric.',
    camera:'Eye-level medium couple portrait, framing the embrace and bouquet.', lighting:'Warm sunlight filtered through garden foliage.',
    style:'Cinematic', lightingPreference:'Golden Hour', posePreference:'Natural', angle:'Eye Level', clothing:'Formal', colors:'Cream and ivory',
    outfit:'Light cream suit and ivory lace dress with a pale pink-and-white bouquet.', instructions:'Keep both faces visible in a natural affectionate glance, and retain the soft floral arch around the couple.'},
  {id:'graduation-01', category:'Graduation', title:'A Proud Campus Moment', people:1, environment:'Outdoor',
    pose:'Stand upright, lightly touch the mortarboard tassel with one hand and hold the rolled diploma in the other.',
    background:'Green campus lawn with leafy trees and a softly blurred building.',
    camera:'Eye-level medium portrait with space above the graduation cap.', lighting:'Soft daylight through trees with a warm edge on the hair.',
    style:'Natural', lightingPreference:'Natural Light', posePreference:'Formal', angle:'Eye Level', clothing:'Formal', colors:'Black and purple',
    outfit:'Black graduation gown and cap with a purple stole, holding a rolled diploma.', instructions:'Keep the cap, tassel, stole and diploma clearly visible; use a proud relaxed smile and gentle background blur.'},
  {id:'portrait-01', category:'Portrait', title:'Warm Lounge Portrait', people:1, environment:'Indoor',
    pose:'Recline comfortably in an armchair with one elbow supported and the hand resting loosely near the temple.',
    background:'Dark lounge with a glowing round lamp, shelves and trailing green plants.',
    camera:'Eye-level seated medium portrait at a slight diagonal.', lighting:'Warm side lighting with a visible amber practical lamp and soft shadows.',
    style:'Cinematic', lightingPreference:'Low Light', posePreference:'Natural', angle:'Eye Level', clothing:'Casual', colors:'Black and beige',
    outfit:'Black open-collar shirt, beige trousers and a wristwatch.', instructions:'Preserve the relaxed hand position and warm moody atmosphere while keeping the eyes and face clearly lit.'},
  {id:'outdoor-01', category:'Outdoor', title:'A Walk Through the Garden', people:1, environment:'Outdoor',
    pose:'Pause mid-walk, hold a backpack strap with one hand, keep the other hand near the pocket and glance toward the flowers.',
    background:'Tree-lined garden walkway bordered by hedges and bright pink flowers.',
    camera:'Eye-level three-quarter portrait with the path receding behind the subject.', lighting:'Soft sun filtered through trees with warm highlights.',
    style:'Natural', lightingPreference:'Natural Light', posePreference:'Candid', angle:'Eye Level', clothing:'Casual', colors:'Olive, white and beige',
    outfit:'Olive overshirt over a white T-shirt, light beige trousers and a backpack.', instructions:'Include the flowering branch near the frame edge and use the walkway as a gentle leading line.'},
  {id:'traditional-01', category:'Traditional', title:'Maroon and Gold Courtyard', people:1, environment:'Outdoor',
    pose:'Stand at a slight angle, raise one hand lightly toward the hair and rest the other near the waist, looking off-camera.',
    background:'Traditional courtyard with carved columns, marigold garlands and a brass lamp.',
    camera:'Eye-level waist-up portrait with the architectural detail at one side.', lighting:'Warm natural side light filtered through courtyard foliage.',
    style:'Traditional', lightingPreference:'Golden Hour', posePreference:'Natural', angle:'Eye Level', clothing:'Traditional', colors:'Maroon and gold',
    outfit:'Maroon sari with ornate gold borders, gold jewelry and white flowers in the hair.', instructions:'Keep sari folds, gold border and floral hair decoration detailed without overpowering the face; preserve the courtyard atmosphere.'},
  {id:'fashion-01', category:'Fashion', title:'Black Denim Street Style', people:1, environment:'Outdoor',
    pose:'Lean casually against the wall with hands near the pockets and turn the face slightly toward the light.',
    background:'Pale exterior wall beside dark window frames and leafy plants.',
    camera:'Eye-level three-quarter fashion portrait with a slight diagonal body angle.', lighting:'Dappled daylight casting soft leaf shadows on the wall.',
    style:'Natural', lightingPreference:'Natural Light', posePreference:'Natural', angle:'Eye Level', clothing:'Streetwear', colors:'Black and white',
    outfit:'Black denim jacket over a white T-shirt, dark trousers, sunglasses and a chain necklace.', instructions:'Emphasize the relaxed silhouette, jacket texture and clean wall composition; retain natural leaf shadows.'},
  {id:'friends-01', category:'Friends', title:'Together on the Garden Steps', people:5, environment:'Outdoor',
    pose:'Arrange five friends at two heights on low steps, leaning toward each other with relaxed arms and playful smiles.',
    background:'Garden or campus steps surrounded by trees, lawn and a softly blurred building.',
    camera:'Eye-level group portrait with everyone close together and all five faces visible.', lighting:'Soft warm daylight under leafy trees.',
    style:'Natural', lightingPreference:'Natural Light', posePreference:'Candid', angle:'Eye Level', clothing:'Casual', colors:'White, black, blue and muted green',
    outfit:'Coordinated casual shirts and tops with jeans or light trousers; avoid matching uniforms.', instructions:'Keep exactly five people in a friendly staggered arrangement. Avoid overlapping faces and preserve individual hands and natural expressions.'},
  // Missing from the supplied folder: do not invent image-specific metadata.
  {id:'beach-01', category:'Beach', title:'Beach inspiration', available:false, reason:'Original image awaiting restoration and content review.'},
].map(sample => ({...sample, image:`/images/explore/${sample.id}.png`, available:sample.available !== false}));

export function getExploreSample(id) { return exploreSamples.find(s => s.id === id && s.available) || null; }
export function filterExploreSamples(query='', category='All') {
  const needle=query.trim().toLowerCase();
  return exploreSamples.filter(s => (category === 'All' || s.category === category) &&
    [s.title,s.category,s.pose,s.background,s.camera,s.lighting,s.outfit,s.style].filter(Boolean).join(' ').toLowerCase().includes(needle));
}
export function samplePlan(sample) {
  return {photography_type:sample.title,people_count:sample.people,environment:sample.environment,location:sample.background,
    preferences:{photography_style:sample.style,lighting_preference:sample.lightingPreference,pose_preference:sample.posePreference,
      camera_angle_preference:sample.angle,clothing_style:sample.clothing,outfit_color:sample.colors,outfit_details:sample.outfit,
      extra_instructions:`Pose: ${sample.pose}\nCamera: ${sample.camera}\nLighting: ${sample.lighting}\n${sample.instructions}`}};
}
