// Stimulation Pad Guide Ring
// Holds a 2" (50mm) round TENS electrode pad in position
//
// Parameters
pad_diameter = 50;      // Standard 2" TENS pad
ring_width = 4;         // Ring wall width (mm)
ring_height = 2;        // Ring height — thin to be flexible (mm)
base_thickness = 1.0;   // Flat base for velcro attachment (mm)
base_extension = 8;     // Base extends beyond ring for attachment (mm)
slot_width = 2.5;       // Velcro/sewing slot width (mm)
slot_length = 10;       // Velcro/sewing slot length (mm)
$fn = 60;

module guide_ring() {
    difference() {
        // Outer ring + base
        union() {
            // Ring
            cylinder(d=pad_diameter + ring_width * 2, h=ring_height);

            // Base tabs (4 directions for attachment)
            for (angle = [0, 90, 180, 270])
                rotate([0, 0, angle])
                    translate([pad_diameter/2 + ring_width + base_extension/2 - 2, 0, 0])
                        hull() {
                            cylinder(r=base_extension/2, h=base_thickness);
                            translate([-base_extension/2, 0, 0])
                                cylinder(r=1, h=base_thickness);
                        }
        }

        // Inner opening (pad sits here)
        translate([0, 0, -0.1])
            cylinder(d=pad_diameter - 2, h=ring_height + 0.2);

        // Flex cuts (allow ring to conform to forearm curvature)
        for (angle = [45, 135, 225, 315])
            rotate([0, 0, angle])
                translate([pad_diameter/2, 0, -0.1])
                    cube([ring_width + 1, 1.5, ring_height + 0.2], center=true);

        // Attachment slots in base tabs
        for (angle = [0, 90, 180, 270])
            rotate([0, 0, angle])
                translate([pad_diameter/2 + ring_width + base_extension/2 - 2, 0, -0.1])
                    hull() {
                        translate([-slot_length/4, 0, 0])
                            cylinder(r=slot_width/2, h=base_thickness + 0.2);
                        translate([slot_length/4, 0, 0])
                            cylinder(r=slot_width/2, h=base_thickness + 0.2);
                    }
    }
}

guide_ring();
