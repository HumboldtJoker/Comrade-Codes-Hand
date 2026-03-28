// Cable Management Clip
// Routes cable bundle along forearm sleeve
//
// Parameters
cable_bundle_d = 8;     // Estimated bundle diameter for 6 cables (mm)
clip_wall = 1.5;        // Clip wall thickness (mm)
base_w = 18;            // Base width (mm)
base_l = 12;            // Base length (mm)
base_t = 1.2;           // Base thickness (mm)
sew_hole_d = 2.5;       // Sewing hole diameter (mm)
gap = 3;                // Opening gap for snap-in (mm)
$fn = 40;

module cable_clip() {
    difference() {
        union() {
            // Base plate
            hull() {
                for (x = [-base_l/2 + 2, base_l/2 - 2])
                    for (y = [-base_w/2 + 2, base_w/2 - 2])
                        translate([x, y, 0])
                            cylinder(r=2, h=base_t);
            }

            // Cable channel (C-shape)
            translate([0, 0, base_t])
                difference() {
                    cylinder(d=cable_bundle_d + clip_wall * 2, h=cable_bundle_d/2 + clip_wall);

                    // Inner channel
                    translate([0, 0, -0.1])
                        cylinder(d=cable_bundle_d + 0.4, h=cable_bundle_d/2 + clip_wall + 0.2);

                    // Snap-in gap (top)
                    translate([-gap/2, 0, cable_bundle_d/4])
                        cube([gap, cable_bundle_d + clip_wall * 2 + 1, cable_bundle_d], center=true);
                }
        }

        // Sewing holes (2)
        for (y = [-base_w/2 + 3, base_w/2 - 3])
            translate([0, y, -0.1])
                cylinder(d=sew_hole_d, h=base_t + 0.2);
    }
}

cable_clip();
