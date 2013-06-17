use Data::Dumper;

$str = "opt\topt2=attr\tattr2";
$attrstr = "attrstr";

my %nameattr;
$nameattr{1} = { map { split /=/, $str, 2 } split /\t/, $attrstr };

print Dumper(\%nameattr);
