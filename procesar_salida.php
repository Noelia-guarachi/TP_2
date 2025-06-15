
<?php
if ($_SERVER["REQUEST_METHOD"] == "POST") {
    $dni = escapeshellarg($_POST['dni']);  
    $output = shell_exec("python marcar_salida.py $dni");  
    echo "<pre>$output</pre>";  
} else {
    echo "Acceso inválido.";
}
?>
