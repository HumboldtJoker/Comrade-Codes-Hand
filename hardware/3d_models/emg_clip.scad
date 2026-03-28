// EMG Sensor Clip for BioAmp Candy
// Snap-fit bracket with sleeve attachment base
//
// Parameters — adjust for fit
board_length = 25;      // BioAmp Candy length (mm)
board_width = 10;       // BioAmp Candy width (mm)
board_thickness = 1.6;  // PCB thickness (mm)
wall = 1.2;             // Wall thickness (mm)
clip_height = 5;        // Total clip height above sleeve (mm)
base_width = 30;        // Base footprint width (mm)
base_length = 35;       // Base footprint length (mm)
base_thickness = 1.5;   // Base plate thickness (mm)
slot_width = 3;         // Sewing/velcro slot width (mm)
slot_length = 12;       // Sewing/velcro slot length (mm)
lip = 0.6;              // Snap-fit lip overhang (mm)
$fn = 40;

module base_plate() {
    difference() {
        // Rounded rectangle base
        hull() {
            for (x = [-base_length/2 + 3, base_length/2 - 3])
                for (y = [-base_width/2 + 3, base_width/2 - 3])
                    translate([x, y, 0])
                        cylinder(r=3, h=base_thickness);
        }

        // Sewing/velcro attachment slots (4 corners)
        for (x = [-base_length/2 + 5, base_length/2 - 5])
            for (y = [-base_width/2 + 4, base_width/2 - 4])
                translate([x, y, -0.1])
                    hull() {
                        translate([-slot_length/2, 0, 0])
                            cylinder(r=slot_width/2, h=base_thickness + 0.2);
                        translate([slot_length/2, 0, 0])
                            cylinder(r=slot_width/2, h=base_thickness + 0.2);
                    }
    }
}

module clip_walls() {
    cradle_h = clip_height - base_thickness;

    translate([0, 0, base_thickness]) {
        difference() {
            // Outer walls
            hull() {
                for (x = [-(board_length/2 + wall), (board_length/2 + wall)])
                    for (y = [-(board_width/2 + wall), (board_width/2 + wall)])
                        translate([x > 0 ? x - 1 : x + 1, y > 0 ? y - 1 : y + 1, 0])
                            cylinder(r=1, h=cradle_h);
            }

            // Inner cavity
            translate([0, 0, -0.1])
                cube([board_length + 0.4, board_width + 0.4, cradle_h + 0.2], center=true);

            // Cable exit slot (one short end)
            translate([board_length/2 + wall, 0, cradle_h/2])
                cube([wall * 3, board_width * 0.6, cradle_h + 0.2], center=true);
        }

        // Snap-fit lips (inward bumps to hold PCB)
        for (y = [-(board_width/2 + 0.2), (board_width/2 + 0.2 - lip)])
            translate([-board_length/4, y, cradle_h - board_thickness - lip])
                cube([board_length/2, lip, lip]);
    }
}

// Assemble
base_plate();
clip_walls();
