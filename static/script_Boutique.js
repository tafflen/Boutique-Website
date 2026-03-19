
// document.addEventListener("DOMContentLoaded", () => {
//     const cartItems = document.querySelector(".cart-page");
//     const checkoutBtn = document.querySelector(".checkout");



//     // Remove item from cart
//     cartItems.addEventListener("click", (event) => {
//         if (event.target.classList.contains("remove")) {
//             event.target.parentElement.remove();
//             updateCart();
//         }
//     });



//     // Checkout button event
//     checkoutBtn.addEventListener("click", () => {
//         alert("Your order has been placed! The owner has been notified.");
//     });



//     // Update total price
//     function updateCart() {
//         let total = 0;
//         document.querySelectorAll(".cart-item").forEach((item) => {
//             let price = parseFloat(item.querySelector("p:nth-of-type(2)").textContent.replace("$", ""));
//             let quantity = parseInt(item.querySelector("input").value);
//             total += price * quantity;
//         });
//         document.querySelector(".checkout").textContent = `Proceed to Checkout ($${total.toFixed(2)})`;
//     }



//     // Update total when quantity changes
//     document.querySelectorAll(".cart-item input").forEach((input) => {
//         input.addEventListener("change", updateCart);
//     });
// });



//     //signIn fn
// function signIn() {
//     let email = document.getElementById('user-email').value;
//     if (email) {
//         localStorage.setItem('userEmail', email);
//         alert('Signed in successfully!');
//         document.getElementById('signin-modal').style.display = 'none';
//     }
// }



//      //show & close the product details
// function showProductDetails(name, price, img) {
//     document.getElementById('product-name').innerText = name;
//     document.getElementById('product-price').innerText = `$${price}`;
//     document.getElementById('product-img').src = img;
//     document.getElementById('product-details').style.display = 'block';
// }

// function closeProductDetails() {
//     document.getElementById('product-details').style.display = 'none';
// }




//       //Buy now
// function buyNow() {
//     let email = localStorage.getItem('userEmail');
//     if (!email) {
//         alert('Please sign in to continue.');
//         document.getElementById('signin-modal').style.display = 'block';
//         return;
//     }
//     alert('Proceeding to checkout...');
// }
// let productName = document.getElementById('product-name').innerText
// let productPrice = document.getElementById('product-price').innerText;
// let userAddress = prompt('Enter your delivery address:');

// if (userAddress) {
//     alert(`Order placed!\nProduct: ${productName}\nPrice: ${productPrice}\nDelivery Address: ${userAddress}`);
//     sendOrderNotification(email, productName, productPrice, userAddress);
// }




//       //sending order notification
// function sendOrderNotification(email, productName, productPrice, userAddress) {
// console.log(`Sending order details to owner...`);
// console.log(`User Email: ${email}`);
// console.log(`Product: ${productName}`);
// console.log(`Price: ${productPrice}`);
// console.log(`Delivery Address: ${userAddress}`);
// alert('Order details sent to the owner.');
// }









// <!--JAVASCRIPT-->
//   <script>
//     function removeItem(button) {
//       const item = button.closest('.item');
//       item.remove();
//     }

//     function moveToCart(button) {
//       const item = button.closest('.item');
//       document.getElementById('cart').appendChild(item);
//       // Optional: change buttons
//       item.querySelector('.move').remove(); // remove move button
//     }

    
//     function loadItems(type, containerId) {
//       const items = JSON.parse(localStorage.getItem(type)) || [];
//       const container = document.getElementById(containerId);

//       items.forEach((item, index) => {
//         const div = document.createElement('div');
//         div.className = 'item';
//         div.innerHTML = `
//           <img src="${item.img}" alt="${item.name}">
//           <div class="item-info">
//             <h4>${item.name}</h4>
//             <p>$${item.price}</p>
//           </div>
//           <div class="item-actions">
//             <button class="remove" onclick="removeItem('${type}', ${index}, this)">Remove</button>
//           </div>
//         `;
//         container.appendChild(div);
//       });
//     }

//     function removeItem(type, index, button) {
//       let items = JSON.parse(localStorage.getItem(type)) || [];
//       items.splice(index, 1); // remove item
//       localStorage.setItem(type, JSON.stringify(items));
//       button.closest('.item').remove();
//     }

//     // Load on page load
//     window.onload = () => {
//       loadItems('wishlist', 'wishlist');
//       loadItems('cart', 'cart');
//     };
  
//   </script>
