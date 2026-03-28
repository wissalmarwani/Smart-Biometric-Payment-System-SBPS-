// frontend/js/main.js
// Navigation and general utilities

// Rediriger vers la page de vérification faciale
function goToVerification() {
    window.location.href = 'verify_face.html';
}

// Vérifier la santé du serveur
async function checkServerHealth() {
    try {
        const response = await fetch('http://127.0.0.1:5000/health');
        const data = await response.json();
        console.log('Serveur OK:', data);
        return data.success;
    } catch (error) {
        console.error('Erreur serveur:', error);
        return false;
    }
}

// Initialiser l'application au chargement
document.addEventListener('DOMContentLoaded', function () {
    checkServerHealth();
});